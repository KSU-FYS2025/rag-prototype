install.packages("rjson")
library(rjson)

# Load the JSON file
json_data <- fromJSON(file = "results/full_agent_full_agent_eval_set_large_5_1781790075.9050326.json")

# Extract queries
queries <- json_data$evalCaseResults
# session_details <- sapply(queries, function(x) x$sessionDetails)

get_timestamps <- function(query) {
  timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  max(timestamps) - min(timestamps)
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

# Build a data frame directly
results <- data.frame(
  user_query = sapply(queries, get_user_query),
  time_delta = sapply(queries, get_timestamps),
  cmds = I(sapply(queries, get_cmds))  # Use I() to store lists in a data frame
)

# Get the user query with the longest time delta
longest_idx <- which.max(results$time_delta)
results$user_query[longest_idx]
results$cmds[longest_idx]

results$cmds[results$cmds == c("resolve_nearest", "resolve_nearest")]

results[which(sapply(queries, function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$
    actualInvocation$
    finalResponse$
    parts[[1]]$text
  cmds <- sapply(fromJSON(response_text)$actions, function(a) a$cmd)
  sum(cmds == "resolve_nearest") == 2
})),]

results[which.max(ifelse(sapply(queries, function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$
    actualInvocation$
    finalResponse$
    parts[[1]]$text
  cmds <- sapply(fromJSON(response_text)$actions, function(a) a$cmd)
  "navigation" %in% cmds
}), results$time_delta, NA)),]

# If you save the JSON to a file, cleaner to load it directly:
query_type_list <- fromJSON(file = "results/ExcelQueries.json")
query_type_map <- setNames(
  sapply(query_type_list, function(x) x[[2]]),
  sapply(query_type_list, function(x) x[[1]])
)

query_type_map <- setNames(
  sapply(query_types_raw, function(x) x[2]),
  sapply(query_types_raw, function(x) x[1])
)

# Join to results
results$query_type <- query_type_map[results$user_query]

# Warn about any unmatched queries
unmatched <- results$user_query[is.na(results$query_type)]
if (length(unmatched) > 0) {
  message("Unmatched queries: ", paste(unmatched, collapse = "\n"))
}

# Order the factor levels logically
results$query_type <- factor(results$query_type, levels = c(
  "Explicit one-step",
  "Implicit one-step",
  "Explicit multi-step",
  "Implicit multi-step",
  "Erroneous prompts"
))

# Boxplot of time delta by query type
boxplot(time_delta ~ query_type, data = results,
        main = "Session Duration by Query Type",
        xlab = "Query Type",
        ylab = "Duration (s)",
        col = c("steelblue", "skyblue", "tomato", "salmon", "goldenrod"),
        las = 2,
        cex.axis = 0.8)

# Graph the results
barplot(
  results$time_delta,
  names.arg = results$cmds,
  las = 2,  # Rotate x-axis labels for better readability
  main = "Time Delta for Each User Query",
  ylab = "Time Delta (seconds)",
  col = "blue"
)

boxplot(
  results$time_delta,
  horizontal = TRUE,
  names = "Time Delta",
  main = "Boxplot of Time Deltas",
  ylab = "Time Delta (seconds)",
  col = "orange"
)

cmds <- table(unlist(results$cmds))

# Calculate Percentages
percentages <- round(100 * cmds / sum(cmds), 1)

# Create label strings
pie_labels <- paste0(names(cmds), " ", percentages, "%")
pie(
  cmds,
  labels = pie_labels,
  main = "Distribution of Commands",
  col = rainbow(length(unique(results$cmds)))
)

cmd_times <- do.call(rbind, lapply(queries, function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$
    actualInvocation$
    finalResponse$
    parts[[1]]$text
  response_json <- fromJSON(response_text)

  timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  runtime <- max(timestamps) - min(timestamps)

  data.frame(
    cmd = sapply(response_json$actions, function(a) a$cmd),
    runtime = runtime
  )
}))

boxplot(runtime ~ cmd, data = cmd_times,
        main = "Runtime by Command Type",
        xlab = "Command",
        ylab = "Runtime (s)",
        col = c("steelblue", "tomato", "seagreen", "goldenrod")
)

get_agent_times <- function(query) {
  events <- query$sessionDetails$events

  timestamps <- sapply(events, function(e) e$timestamp)
  start <- min(timestamps)

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

boxplot(runtime ~ agent, data = agent_times,
        main = "Runtime by Agent",
        xlab = "Agent",
        ylab = "Runtime (s)",
        col = c("steelblue", "tomato", "seagreen", "goldenrod"),
        names = c("Agent 1 - Root", "Agent 2 - triage", "Agent 3 - synthesis", "Agent 4 - response"))

# Create CSV file for user queries, responses, and POI IDs returned
get_poi_ids <- function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$
    actualInvocation$
    finalResponse$
    parts[[1]]$text
  response_json <- fromJSON(response_text)

  ids <- unlist(lapply(response_json$actions, function(a) {
    if (!is.null(a$id)) a$id
    else if (!is.null(a$candidate_ids)) a$candidate_ids
    else if (!is.null(a$suggestions)) sapply(a$suggestions, function(s) s$id)
    else NULL
  }))

  if (is.null(ids)) NA else paste(ids, collapse = ";")
}

get_final_response <- function(query) {
  response_text <- query$evalMetricResultPerInvocation[[1]]$
    actualInvocation$
    finalResponse$
    parts[[1]]$text
  fromJSON(response_text)$response
}

summary_table <- data.frame(
  user_query = results$user_query,
  final_response = sapply(queries, get_final_response),
  poi_ids = sapply(queries, get_poi_ids)
)

write.csv(summary_table, "summary.csv", row.names = FALSE)