install.packages("rjson")
library(rjson)

json_data <- fromJSON(file = "results/full_agent_full_agent_eval_set_large_6_1782221741.784494.json")
queries <- json_data$evalCaseResults

# Load query type mapping from file
query_type_list <- fromJSON(file = "results/ExcelQueries.json")
query_type_map <- setNames(
  sapply(query_type_list, function(x) x[[2]]),
  sapply(query_type_list, function(x) x[[1]])
)

get_timestamps <- function(query) {
  timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  timestamps[length(timestamps)] - timestamps[1]
}

get_user_query <- function(query) {
  events <- query$sessionDetails$events
  user_event <- Filter(function(e) !is.null(e$content$role) && e$content$role == "user", events)
  user_event[[1]]$content$parts[[1]]$text
}

get_cmds <- function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$
    actualInvocation$
    finalResponse$
    parts[[1]]$text
  response_json <- fromJSON(response_text)
  sapply(response_json$actions, function(a) a$cmd)
}

results <- data.frame(
  user_query = sapply(queries, get_user_query),
  time_delta = sapply(queries, get_timestamps),
  cmds = I(sapply(queries, get_cmds))
)

# Join query types
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

# --- Agent timing ---
get_agent_times <- function(query) {
  events <- query$sessionDetails$events
  timestamps <- sapply(events, function(e) e$timestamp)
  start <- timestamps[1]

  agent_events <- Filter(function(e) {
    !is.null(e$usageMetadata) && !is.null(e$author)
  }, events)

  data.frame(
    user_query = events[[1]]$content$parts[[1]]$text,
    agent = sapply(agent_events, function(e) e$author),
    runtime = sapply(agent_events, function(e) e$timestamp - start)
  )
}

agent_times <- do.call(rbind, lapply(queries, get_agent_times))
agent_times$agent <- factor(agent_times$agent,
                            levels = c("root_agent", "triage_agent", "synthesis_agent", "response_agent"))

# --- Plots ---

barplot(
  results$time_delta,
  names.arg = seq_along(results$time_delta),
  las = 2,
  main = "Total Session Duration per Query",
  ylab = "Duration (seconds)",
  col = "steelblue"
)

boxplot(
  results$time_delta,
  horizontal = TRUE,
  main = "Boxplot of Session Durations",
  xlab = "Duration (seconds)",
  col = "orange"
)

cmds <- table(unlist(results$cmds))
percentages <- round(100 * cmds / sum(cmds), 1)
pie_labels <- paste0(names(cmds), " ", percentages, "%")
pie(cmds, labels = pie_labels, main = "Distribution of Commands",
    col = rainbow(length(cmds)))

cmd_times <- do.call(rbind, lapply(queries, function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$
    actualInvocation$
    finalResponse$
    parts[[1]]$text
  response_json <- fromJSON(response_text)
  timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  runtime <- timestamps[length(timestamps)] - timestamps[1]
  data.frame(
    cmd = sapply(response_json$actions, function(a) a$cmd),
    runtime = runtime
  )
}))

boxplot(runtime ~ cmd, data = cmd_times,
        main = "Session Duration by Command Type",
        xlab = "Command",
        ylab = "Duration (s)",
        col = c("steelblue", "tomato", "seagreen", "goldenrod"))

boxplot(runtime ~ agent, data = agent_times,
        main = "Time-to-Response by Agent",
        xlab = "Agent",
        ylab = "Elapsed Time from Session Start (s)",
        col = c("steelblue", "tomato", "seagreen", "goldenrod"),
        names = c("Root", "Triage", "Synthesis", "Response"))

boxplot(time_delta ~ query_type, data = results,
        main = "Session Duration by Query Type",
        xlab = "Query Type",
        ylab = "Duration (s)",
        col = c("steelblue", "skyblue", "tomato", "salmon", "goldenrod"),
        cex.axis = 0.8)