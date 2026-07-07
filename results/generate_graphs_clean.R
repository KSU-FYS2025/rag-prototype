install.packages("rjson")
library(rjson)

json_data <- fromJSON(file = "results/evalset_results/full_agent_full_agent_eval_set_large_10_enabled_1782416910.1893363.json")
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
  session_start <- timestamps[1]

  agent_events <- Filter(function(e) {
    !is.null(e$usageMetadata) && !is.null(e$author)
  }, events)

  agent_end <- sapply(agent_events, function(e) e$timestamp)
  agent_start <- c(session_start, head(agent_end, -1))

  data.frame(
    user_query = events[[1]]$content$parts[[1]]$text,
    agent = sapply(agent_events, function(e) e$author),
    runtime = agent_end - agent_start
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


# 1. Define your vectors
thinking_disabled <- c(58, 6, 4, 7) / 75 * 100
thinking_enabled  <- c(63, 5, 2, 5) / 75 * 100

# 2. Combine as COLUMNS to get 2 bars total, each containing 4 stacked segments
data_matrix <- cbind(thinking_disabled, thinking_enabled)

# 3. Label the 2 bars (columns) and the 4 segments (rows)
colnames(data_matrix) <- c("Disabled", "Enabled")
rownames(data_matrix) <- c("ALL", "SOME", "NONSTANDARD", "NONE")

# 4. Open the PDF device with standard journal dimensions
pdf("../ieee_4_stacked_barplot_shrinked.pdf", width = 4, height = 5)

# 5. Configure Margins
par(oma = c(0, 0, 3, 0))  # Large top outer margin for globally centered title
par(mar = c(2, 4, 2, 8)) # Generous right margin to hold the 4-item legend

# 6. IEEE VGTC High-Contrast, CVD-Safe 4-Color Palette (Okabe-Ito)
# These four colors have distinct luminance profiles for grayscale printing
ieee_colors <- c(
  "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"
)

# 7. Draw the Barplot
barplot(data_matrix,
        xlab = "",
        ylab = "Percentage Occurrences",
        col = ieee_colors,
        ylim = c(0, 100), # Leave headroom for the chart space
        border = "white",
        las = 1) # Keeps Y-axis numbers reading horizontally

# 8. Append the 4-item Legend in the expanded right margin
par(xpd = TRUE)
legend("topleft",
       inset = c(1.02, 0), # Push out into the right margin area
       legend = rownames(data_matrix),
       fill = ieee_colors,
       bty = "n",
       cex = 0.9,
       y.intersp = 1.2) # Clear vertical spacing between legend items

# 9. Add the Globally Centered Title over the absolute center of the PDF
mtext("Percentage Response Encoding\nby Thinking Mode",
      side = 3,
      line = 0,
      outer = TRUE,
      cex = 1.2,
      font = 2)

# 10. Finalize and save the PDF file
dev.off()