library(rjson)

load_results <- function(json_path, query_type_map) {
  json_data <- fromJSON(file = json_path)
  queries   <- json_data$evalCaseResults

  get_timestamps <- function(query) {
    timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
    timestamps[length(timestamps)] - timestamps[1]
  }

  get_user_query <- function(query) {
    events     <- query$sessionDetails$events
    user_event <- Filter(function(e) !is.null(e$content$role) && e$content$role == "user", events)
    user_event[[1]]$content$parts[[1]]$text
  }

  get_cmds <- function(query) {
    response_text <- query$evalMetricResultPerInvocation[[1]]$
      actualInvocation$finalResponse$parts[[1]]$text
    response_json <- fromJSON(response_text)
    sapply(response_json$actions, function(a) a$cmd)
  }

  get_agent_times <- function(query) {
    events     <- query$sessionDetails$events
    timestamps <- sapply(events, function(e) e$timestamp)
    start      <- timestamps[1]
    agent_events <- Filter(function(e) {
      !is.null(e$usageMetadata) && !is.null(e$author)
    }, events)
    data.frame(
      user_query = events[[1]]$content$parts[[1]]$text,
      agent      = sapply(agent_events, function(e) e$author),
      runtime    = sapply(agent_events, function(e) e$timestamp - start)
    )
  }

  results <- data.frame(
    user_query = sapply(queries, get_user_query),
    time_delta = sapply(queries, get_timestamps),
    cmds       = I(sapply(queries, get_cmds))
  )

  results$query_type <- query_type_map[results$user_query]

  unmatched <- results$user_query[is.na(results$query_type)]
  if (length(unmatched) > 0) {
    message("Unmatched queries:\n", paste(unmatched, collapse = "\n"))
  }

  results$query_type <- factor(results$query_type, levels = c(
    "Explicit one-step",
    "Implicit one-step",
    "Explicit multi-step",
    "Implicit multi-step",
    "Erroneous prompts"
  ))

  agent_times <- do.call(rbind, lapply(queries, get_agent_times))
  agent_times$agent <- factor(agent_times$agent,
                              levels = c("root_agent", "triage_agent", "synthesis_agent", "response_agent"))

  cmd_times <- do.call(rbind, lapply(queries, function(query) {
    response_text <- query$evalMetricResultPerInvocation[[1]]$
      actualInvocation$finalResponse$parts[[1]]$text
    response_json <- fromJSON(response_text)
    timestamps    <- sapply(query$sessionDetails$events, function(e) e$timestamp)
    runtime       <- timestamps[length(timestamps)] - timestamps[1]
    data.frame(
      cmd     = sapply(response_json$actions, function(a) a$cmd),
      runtime = runtime
    )
  }))

  list(results = results, agent_times = agent_times, cmd_times = cmd_times)
}

generate_result_grid <- function(data, title, out_file) {
  results     <- data$results
  agent_times <- data$agent_times
  cmd_times   <- data$cmd_times

  cmds_table  <- table(unlist(results$cmds))
  percentages <- round(100 * cmds_table / sum(cmds_table), 1)

  pdf(out_file, width = 7.0, height = 1.8, pointsize = 6, family = "Times")

  par(mfrow = c(1, 6),
      mar   = c(7, 4.5, 2.0, 0.5),
      mgp   = c(2.2, 0.5, 0),
      oma   = c(0, 0, 1.5, 0),
      lwd   = 0.5,
      cex   = 0.6)

  # (a) Duration per query
  bp_a <- barplot(results$time_delta, names.arg = NA, axes = FALSE,
                   col = "steelblue")
  axis(1, at = bp_a, labels = seq_along(results$time_delta), las = 2,
       lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.35)
  axis(2, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  title(ylab = "Duration (s)", cex.lab = 0.6, line = 2.2)
  title(main = "Duration per Query", cex.main = 0.6, line = 0.3)
  box(lwd = 0.5)
  mtext("(a)", side = 1, line = 5.5, cex = 0.6)

  # (b) Overall duration distribution
  boxplot(results$time_delta, horizontal = TRUE, col = "orange",
          axes = FALSE, frame.plot = FALSE,
          boxlwd = 0.5, whisklwd = 0.5, staplelwd = 0.5, outlwd = 0.5, medlwd = 0.5)
  axis(1, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  title(xlab = "Duration (s)", cex.lab = 0.6, line = 2.2)
  title(main = "Duration Distribution", cex.main = 0.6, line = 0.3)
  box(lwd = 0.5)
  mtext("(b)", side = 1, line = 5.5, cex = 0.6)

  # (c) Command distribution
  bp_c <- pie(percentages,
                   col = rainbow(length(cmds_table)),
                   cex = 0.5,
                   labels = paste(percentages, "%")
  )
  legend("bottomright",
			c("answer", "resolve_nearest", "navigation", "clarify"),
			cex = 0.8,
			fill = rainbow(length(cmds_table)))
  # axis(1, at = bp_c, labels = names(cmds_table), las = 2,
  #      lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.45)
  # axis(2, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  # title(ylab = "Percentage (%)", cex.lab = 0.6, line = 2.2)
  title(main = "Command Distribution", cex.main = 0.6, line = 0.3)
  # box(lwd = 0.5)
  mtext("(c)", side = 1, line = 5.5, cex = 0.6)

  # (d) Duration by command type
  boxplot(runtime ~ cmd, data = cmd_times,
          col = c("steelblue", "tomato", "seagreen", "goldenrod"),
          xlab = "", ylab = "",
          axes = FALSE, frame.plot = FALSE,
          boxlwd = 0.5, whisklwd = 0.5, staplelwd = 0.5, outlwd = 0.5, medlwd = 0.5)
  axis(1, at = seq_along(levels(factor(cmd_times$cmd))), labels = levels(factor(cmd_times$cmd)),
       las = 1, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  axis(2, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  title(ylab = "Duration (s)", cex.lab = 0.6, line = 2.2)
  title(main = "Duration by Command", cex.main = 0.6, line = 0.3)
  box(lwd = 0.5)
  mtext("(d)", side = 1, line = 5.5, cex = 0.6)

  # (e) Time-to-response by agent
  boxplot(runtime ~ agent, data = agent_times,
          col = c("steelblue", "tomato", "seagreen", "goldenrod"),
          xlab = "", ylab = "",
          axes = FALSE, frame.plot = FALSE,
          boxlwd = 0.5, whisklwd = 0.5, staplelwd = 0.5, outlwd = 0.5, medlwd = 0.5)
  axis(1, at = 1:4, labels = c("Root", "Triage", "Synth.", "Resp."),
       las = 1, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  axis(2, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  title(ylab = "Elapsed Time (s)", cex.lab = 0.6, line = 2.2)
  title(main = "Time-to-Response", cex.main = 0.6, line = 0.3)
  box(lwd = 0.5)
  mtext("(e)", side = 1, line = 5.5, cex = 0.6)

  # (f) Duration by query type
  boxplot(time_delta ~ query_type, data = results,
          col = c("steelblue", "skyblue", "tomato", "salmon", "goldenrod"),
          xlab = "", ylab = "",
          axes = FALSE, frame.plot = FALSE,
          boxlwd = 0.5, whisklwd = 0.5, staplelwd = 0.5, outlwd = 0.5, medlwd = 0.5)
  par(las=1)
  axis(1, at = 1:5, labels = c("Explicit\none-step", "Implicit\none-step", "Explicit\nmulti-step", "Implicit\nmulti-step", "Erroneous"),
       las = 1, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.45)
  axis(2, lwd = 0.5, lwd.ticks = 0.5, cex.axis = 0.55)
  title(ylab = "Duration (s)", cex.lab = 0.6, line = 2.2)
  title(main = "Duration by Query Type", cex.main = 0.6, line = 0.3)
  box(lwd = 0.5)
  mtext("(f)", side = 1, line = 5.5, cex = 0.6)

  mtext(title, outer = TRUE, cex = 0.9, font = 2)

  dev.off()
}

# --- Load query type map (shared between both runs) ---
query_type_list <- fromJSON(file = "results/ExcelQueries.json")
query_type_map  <- setNames(
  sapply(query_type_list, function(x) x[[2]]),
  sapply(query_type_list, function(x) x[[1]])
)

# --- Load both runs ---
run_a <- load_results(
  "results/evalset_results/full_agent_full_agent_eval_set_large_10_disabled_1782415557.690652.json",
  query_type_map
)

run_b <- load_results(
  "results/evalset_results/full_agent_full_agent_eval_set_large_10_enabled_1782416910.1893363.json",
  query_type_map
)

# --- Export each as a full-width strip ---
generate_result_grid(run_a, "Run A", "grid_run_a.pdf")
generate_result_grid(run_b, "Run B", "grid_run_b.pdf")