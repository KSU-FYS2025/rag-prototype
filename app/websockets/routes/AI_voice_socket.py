from app.AI.full_agent.actions_agent.schema import AnswerAction
import asyncio
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.adk import Runner
from google.adk.agents import LiveRequestQueue, RunConfig
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed

from app.AI import audio_relay
from app.AI.full_agent.actions_agent.schema import (
    ActionsAgentOutput,
    ClarifyAction,
    ResolveNearestAction,
    NavigationAction,
)
from app.AI.full_agent.clarify_agent.schema import ClarifyOutput
from app.AI.audio_relay.tools import pending_clarifications
from app.AI.mock_frontend.agent import resolution_helper


class SampleAIAudioHandler:
    app_name = "RagPrototype"

    agent = audio_relay.agent.root_agent

    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=InMemorySessionService(),
    )

    next_plan_id = "p0"

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.chunk_count = 0
        # Fresh session per connection so stale history (e.g. unanswered
        # function calls) from a previous connection is never replayed.
        self.test_credentials = {
            "app_name": self.app_name,
            "user_id": "test_u_2",
            "session_id": f"test_s_{uuid.uuid4().hex}",
        }

        self.plan: ActionsAgentOutput | None = None
        self.plan_id = ""
        # True while a clarify question is waiting on the user's answer
        self.awaiting_answer = False
        # Order of the resolve_nearest sent to Unity that hasn't come back yet
        self.nearest_in_flight: int | None = None
        # Unity asked for the next action while it was still a resolve_nearest
        self.next_requested = False

    async def get_session(self):
        session = await self.runner.session_service.get_session(**self.test_credentials)

        if not session:
            await self.runner.session_service.create_session(**self.test_credentials)

        self.run_config = RunConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        self.queue = LiveRequestQueue()

    async def handle(self):
        await self.websocket.accept()
        await self.get_session()

        tasks = [
            asyncio.create_task(self.client_stream()),
            asyncio.create_task(self.adk_stream()),
        ]

        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            self.queue.close()
            pending_clarifications.pop(self.test_credentials["session_id"], None)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        for task in done:
            if not task.cancelled():
                task.result()

    async def client_stream(self):
        try:
            while True:
                message = await self.websocket.receive()

                if message["type"] == "websocket.disconnect":
                    return

                if message.get("bytes") is not None:
                    self.queue.send_realtime(
                        types.Blob(
                            data=message["bytes"], mime_type="audio/pcm;rate=16000"
                        )
                    )
                elif message.get("text") is not None:
                    payload = json.loads(message["text"])
                    await self.resolve_client_event(payload)

        except WebSocketDisconnect:
            return

    async def resolve_client_event(self, payload):
        match payload:
            case {"event": "stop"}:
                self.queue.send_audio_stream_end()
            case {"event": "text", "text": text}:
                self.queue.send_content(
                    types.Content(role="user", parts=[types.Part(text=text)])
                )

            case {"event": "next_action", "plan_id": plan_id}:
                if plan_id == self.plan_id:
                    await self.resolve_next_action()

            case {
                "event": "resolve_nearest_result",
                "plan_id": plan_id,
                "request_id": int(request_id),
                "id": int(poi_id),
            }:
                if plan_id == self.plan_id:
                    await self.apply_nearest_result(request_id, poi_id)

            case {
                "event": "action_done",
                "plan_id": plan_id,
                "request_id": int(request_id),
            }:
                if plan_id == self.plan_id:
                    self.finish_action(request_id)

            case _:
                logging.warning(f"Unknown message: {payload}")

    @staticmethod
    def _log_event(event: Event):
        ts = datetime.now().isoformat(timespec="milliseconds")

        for fc in event.get_function_calls():
            logging.info(
                f"[{ts}] FUNCTION_CALL id={fc.id} name={fc.name} args={fc.args} "
                f"author={event.author} branch={event.branch} invocation={event.invocation_id}"
            )

        for fr in event.get_function_responses():
            logging.info(
                f"[{ts}] FUNCTION_RESPONSE id={fr.id} name={fr.name} response={fr.response} "
                f"author={event.author} branch={event.branch}"
            )

        if event.interrupted:
            logging.info(f"[{ts}] INTERRUPTED")

        if event.input_transcription and event.input_transcription.text:
            logging.info(
                f"[{ts}] USER_TRANSCRIPT finished={bool(event.input_transcription.finished)} "
                f"text={event.input_transcription.text!r}"
            )

        if event.output_transcription and event.output_transcription.text:
            logging.info(
                f"[{ts}] AGENT_TRANSCRIPT finished={bool(event.output_transcription.finished)} "
                f"text={event.output_transcription.text!r}"
            )

        if event.turn_complete:
            logging.info(f"[{ts}] TURN_COMPLETE")

    async def adk_stream(self):
        try:
            async for event in self.runner.run_live(
                user_id=self.test_credentials["user_id"],
                session_id=self.test_credentials["session_id"],
                live_request_queue=self.queue,
                run_config=self.run_config,
            ):
                self._log_event(event)

                if event.interrupted:
                    await self.websocket.send_json({"event": "interrupted"})

                for fr in event.get_function_responses():
                    if fr.response:
                        await self.websocket.send_json(
                            {
                                "event": "function_call",
                                "function_name": fr.name,
                                "return": {**fr.response},
                            }
                        )

                        if fr.name == "navigate":
                            try:
                                validated = ActionsAgentOutput.model_validate(
                                    fr.response
                                )
                                # If self.plan is not None, that means that there's already a plan running, and we need
                                # to make sure that the frontend knows that it's been canceled
                                if self.plan is not None:
                                    await self.websocket.send_json(
                                        {"event": "cancel", "plan_id": self.plan_id}
                                    )

                                current_int = int(self.next_plan_id[1:])
                                next_int = current_int + 1
                                self.plan_id = self.next_plan_id
                                self.next_plan_id = f"p{next_int}"

                                self.plan = validated
                                self.plan.actions.sort(key=lambda a: a.order)
                                self.awaiting_answer = False
                                self.nearest_in_flight = None
                                self.next_requested = False

                                self.update_pending_clarification()
                                await self.send_resolve_nearest()

                            except ValidationError as e:
                                logging.warning(
                                    f"Response could not be validated!\n{fr.response}\n{e}"
                                )

                        # An error response leaves the plan unchanged
                        if (
                            fr.name == "resolve_clarification"
                            and "action" in fr.response
                        ):
                            try:
                                validated = ClarifyOutput.model_validate(
                                    {"action": fr.response["action"]}
                                ).action

                                if self.plan is not None:
                                    for index, action in enumerate(self.plan.actions):
                                        if action.order == validated.order:
                                            self.plan.actions[index] = validated
                                            break

                                    self.awaiting_answer = False
                                    self.update_pending_clarification()
                                    await self.send_resolve_nearest()

                            except ValidationError as e:
                                logging.warning(
                                    f"Response could not be validated!\n{fr.response}\n{e}"
                                )

                if event.input_transcription and event.input_transcription.text:
                    await self.websocket.send_json(
                        {
                            "event": "user_transcript",
                            "text": event.input_transcription.text,
                            "finished": bool(event.input_transcription.finished),
                        }
                    )

                if event.output_transcription and event.output_transcription.text:
                    await self.websocket.send_json(
                        {
                            "event": "agent_transcript",
                            "text": event.output_transcription.text,
                            "finished": bool(event.output_transcription.finished),
                        }
                    )

                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.data:
                            await self.websocket.send_bytes(part.inline_data.data)
                if event.turn_complete:
                    await self.websocket.send_json({"event": "turn_complete"})
        except APIError as e:
            logging.error(
                f"[{datetime.now().isoformat(timespec='milliseconds')}] live session APIError "
                f"code={e.code} status={e.status} message={e.message}"
            )
            try:
                await self.websocket.send_json(
                    {"event": "error", "code": e.code, "message": e.message}
                )
            except Exception:
                pass
        except ConnectionClosed as e:
            code = e.rcvd.code if e.rcvd else None
            reason = e.rcvd.reason if e.rcvd else str(e)
            logging.error(
                f"[{datetime.now().isoformat(timespec='milliseconds')}] live connection closed "
                f"code={code} reason={reason}"
            )
            try:
                await self.websocket.send_json(
                    {"event": "error", "code": code, "message": reason}
                )
            except Exception:
                pass

    async def resolve_next_action(self):
        """Called when Unity asks for the next action."""
        if self.plan is None or self.awaiting_answer:
            return

        result = resolution_helper(self.plan)
        if isinstance(result, Event):
            return

        index, _ = result
        match self.plan.actions[index]:
            case ResolveNearestAction():
                # It's already with Unity; apply_nearest_result sends the next
                # action once the result comes back.
                self.next_requested = True
                await self.send_resolve_nearest()

            case AnswerAction() as action:
                self.plan.actions.remove(action)
                self.notify(f"[navigation update] [answer] {action.text}")

            case ClarifyAction() as action:
                self.awaiting_answer = True
                self.notify(f"[navigation update] [question] {action.prompt}")

            case NavigationAction() as action:
                await self.websocket.send_json(
                    {
                        "event": "navigation",
                        "plan_id": self.plan_id,
                        "request_id": action.order,
                        "id": action.id,
                        "target_label": action.target_label,
                    }
                )

    async def send_resolve_nearest(self):
        """Sends the first resolve_nearest, as long as no clarify or other resolve_nearest comes before it."""
        if self.plan is None:
            return

        # The POI the user will be coming from, or None for their current position
        from_id = None
        for action in self.plan.actions:
            if isinstance(action, NavigationAction):
                from_id = action.id
            elif isinstance(action, ClarifyAction):
                return
            elif isinstance(action, ResolveNearestAction):
                if self.nearest_in_flight != action.order:
                    self.nearest_in_flight = action.order
                    await self.websocket.send_json(
                        {
                            "event": "resolve_nearest",
                            "plan_id": self.plan_id,
                            "request_id": action.order,
                            "candidate_ids": action.candidate_ids,
                            "from_id": from_id,
                            "target_label": action.target_label,
                        }
                    )
                return

    async def apply_nearest_result(self, order: int, poi_id: int):
        """Handles Unity's resolve_nearest_result."""
        if self.plan is None:
            return

        for index, action in enumerate(self.plan.actions):
            if action.order == order and isinstance(action, ResolveNearestAction):
                self.plan.actions[index] = NavigationAction(
                    order=order,
                    id=poi_id,
                    target_label=action.target_label,
                    response=f"Guiding you to the nearest {action.target_label}.",
                )
                break

        self.nearest_in_flight = None
        await self.send_resolve_nearest()

        if self.next_requested:
            self.next_requested = False
            await self.resolve_next_action()

    def finish_action(self, order: int):
        """Handles Unity's action_done."""
        if self.plan is None:
            return
        self.plan.actions = [a for a in self.plan.actions if a.order != order]

    def update_pending_clarification(self):
        """Points resolve_clarification at the plan's first clarify, if it has one."""
        session_id = self.test_credentials["session_id"]
        pending_clarifications.pop(session_id, None)

        if self.plan is None:
            return
        for action in self.plan.actions:
            if isinstance(action, ClarifyAction):
                pending_clarifications[session_id] = action
                return

    def notify(self, text: str):
        self.queue.send_content(
            types.Content(role="user", parts=[types.Part(text=text)])
        )

    async def on_disconnect(self):
        pass
