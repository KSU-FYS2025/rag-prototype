library(rjson)

json_data <- fromJSON(file = "results/full_agent_full_agent_eval_set_large_6_1782221741.784494.json")
queries <- json_data$evalCaseResults

# Fix: use first and last event timestamp within the session (not min/max across all)
get_timestamps <- function(query) {
  events    <- query$sessionDetails$events
  timestamps <- sapply(events, function(e) e$timestamp)
  # First event = user message, last event = final agent response
  timestamps[length(timestamps)] - timestamps[1]
}

get_user_query <- function(query) {
  events     <- query$sessionDetails$events
  user_event <- Filter(function(e) !is.null(e$content$role) && e$content$role == "user", events)
  user_event[[1]]$content$parts[[1]]$text
}

get_cmds <- function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$actualInvocation$finalResponse$parts[[1]]$text
  response_json <- fromJSON(response_text)
  sapply(response_json$actions, function(a) a$cmd)
}

results <- data.frame(
  user_query = sapply(queries, get_user_query),
  time_delta = sapply(queries, get_timestamps),
  cmds       = I(sapply(queries, get_cmds))
)

# Agent-level timing: time elapsed from session start to each agent's response
get_agent_times <- function(query) {
  events     <- query$sessionDetails$events
  timestamps <- sapply(events, function(e) e$timestamp)
  start      <- timestamps[1]  # Fix: anchor to first event (user message), not min()

  agent_events <- Filter(function(e) {
    !is.null(e$usageMetadata) && !is.null(e$author)
  }, events)

  data.frame(
    user_query = events[[1]]$content$parts[[1]]$text,
    agent      = sapply(agent_events, function(e) e$author),
    runtime    = sapply(agent_events, function(e) e$timestamp - start)
  )
}

agent_times <- do.call(rbind, lapply(queries, get_agent_times))
agent_times$agent <- factor(agent_times$agent,
                            levels = c("root_agent", "triage_agent", "synthesis_agent", "response_agent"))

# --- Plots ---

barplot(
  results$time_delta,
  names.arg = seq_along(results$time_delta),
  las  = 2,
  main = "Total Session Duration per Query",
  ylab = "Duration (seconds)",
  col  = "steelblue"
)

boxplot(
  results$time_delta,
  horizontal = TRUE,
  main = "Boxplot of Session Durations",
  xlab = "Duration (seconds)",
  col  = "orange"
)

cmds        <- table(unlist(results$cmds))
percentages <- round(100 * cmds / sum(cmds), 1)
pie_labels  <- paste0(names(cmds), " ", percentages, "%")
pie(cmds, labels = pie_labels, main = "Distribution of Commands",
    col = rainbow(length(cmds)))

cmd_times <- do.call(rbind, lapply(queries, function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$actualInvocation$finalResponse$parts[[1]]$text
  response_json <- fromJSON(response_text)
  timestamps    <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  runtime       <- timestamps[length(timestamps)] - timestamps[1]  # Fix: consistent with above
  data.frame(
    cmd     = sapply(response_json$actions, function(a) a$cmd),
    runtime = runtime
  )
}))

boxplot(runtime ~ cmd, data = cmd_times,
        main = "Session Duration by Command Type",
        xlab = "Command",
        ylab = "Duration (s)",
        col  = c("steelblue", "tomato", "seagreen", "goldenrod"))

boxplot(runtime ~ agent, data = agent_times,
        main  = "Time-to-Response by Agent",
        xlab  = "Agent",
        ylab  = "Elapsed Time from Session Start (s)",
        col   = c("steelblue", "tomato", "seagreen", "goldenrod"),
        names = c("Root", "Triage", "Synthesis", "Response"))

json_data <- fromJSON(file = "results/full_agent_full_agent_eval_set_large_6_1782221741.784494.json")
queries <- json_data$evalCaseResults
user_queries <- sapply(queries, get_user_query)
grep("tutoring", user_queries, value = TRUE, ignore.case = TRUE)

idx <- grep("tutoring", user_queries, ignore.case = TRUE)[1]  # take first match
events <- queries[[idx]]$sessionDetails$events
timestamps <- sapply(events, function(e) e$timestamp)
cat("Delta:", timestamps[length(timestamps)] - timestamps[1], "\n")
cat("Timestamps:", paste(timestamps, collapse = ", "), "\n")

inv <- queries[[idx]]$evalMetricResultPerInvocation[[1]]$actualInvocation
cat("creationTimestamp:", inv$creationTimestamp, "\n")
cat("Last event:", timestamps[length(timestamps)], "\n")
cat("Delta:", timestamps[length(timestamps)] - inv$creationTimestamp, "\n")

inv <- queries[[idx]]$evalMetricResultPerInvocation[[1]]$actualInvocation

cat("creationTimestamp:", inv$creationTimestamp, "\n")
cat("All top-level fields:", paste(names(inv), collapse = ", "), "\n")

# Check the expected invocation too
exp <- queries[[idx]]$evalMetricResultPerInvocation[[1]]$expectedInvocation
cat("Expected creationTimestamp:", exp$creationTimestamp, "\n")
cat("Expected top-level fields:", paste(names(exp), collapse = ", "), "\n")

# Also check top-level fields on the eval case itself
cat("Eval case fields:", paste(names(queries[[idx]]), collapse = ", "), "\n")

# Find the earliest timestamp across ALL sessions
all_first_timestamps <- sapply(queries, function(q) {
  timestamps <- sapply(q$sessionDetails$events, function(e) e$timestamp)
  timestamps[1]
})

global_start <- min(all_first_timestamps)
cat("Global start:", global_start, "\n")

# Recompute deltas from global start to each session's last event
results$time_delta_global <- sapply(queries, function(q) {
  timestamps <- sapply(q$sessionDetails$events, function(e) e$timestamp)
  timestamps[length(timestamps)] - global_start
})

cat("Tutoring delta:", results$time_delta_global[idx], "\n")

cat("Min timestamp:", min(timestamps), "\n")
cat("Max timestamp:", max(timestamps), "\n")
cat("Delta:", max(timestamps) - min(timestamps), "\n")