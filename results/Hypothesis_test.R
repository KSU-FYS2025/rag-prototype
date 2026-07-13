install.packages("nortest")
library(nortest)
library(rjson)
json_data_disabled <- fromJSON(file = "results/evalset_results/full_agent_full_agent_eval_set_large_12_disabled_1783532216.7194827.json")
json_data_enabled <- fromJSON(file = "results/evalset_results/full_agent_full_agent_eval_set_large_12_enabled_1783518451.6002152.json")

# First hypothesis test: Are the query times for the evaluation with thinking enabled greater than the evaluation with
# thinking disabled?
# Mean of queries_disabled = approx. 7.616
# H0: mu = 7.616
# H1: mu < 7.616

queries_disabled <- json_data_disabled$evalCaseResults
queries_enabled <- json_data_enabled$evalCaseResults

get_timestamps <- function(query) {
  timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  timestamps[length(timestamps)] - timestamps[1]
}

get_user_query <- function(query) {
  events <- query$sessionDetails$events
  user_event <- Filter(function(e) !is.null(e$content$role) && e$content$role == "user", events)
  user_event[[1]]$content$parts[[1]]$text
}

get_timestamps_enabled <- function(query) {
  timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  timestamps[length(timestamps)] - timestamps[1]
}

get_user_query_enabled <- function(query) {
  events <- query$sessionDetails$events
  user_event <- Filter(function(e) !is.null(e$content$role) && e$content$role == "user", events)
  tail(user_event[[1]]$content$parts, 1)[[1]]$text
}

time_delta_disabled <- sapply(queries_disabled, get_timestamps)
time_delta_enabled <- sapply(queries_enabled, get_timestamps_enabled)

queries_disabled_frame <- sapply(queries_disabled, get_user_query)
queries_enabled_frame <- sapply(queries_enabled, get_user_query_enabled)

df_disabled <- data.frame(queries = queries_disabled_frame, time_deltas = time_delta_disabled)
df_enabled <- data.frame(queries = queries_enabled_frame, time_deltas = time_delta_enabled)

max(df_disabled$time_deltas)
max_spot_disabled <- which.max(df_disabled$time_deltas)
df_disabled$queries[max_spot_disabled]

max(df_enabled$time_deltas)
max_spot_enabled <- which.max(df_enabled$time_deltas)
df_enabled$queries[max_spot_enabled]

shapiro.test(time_delta_disabled)
shapiro.test(time_delta_enabled)

qqnorm(time_delta_disabled); qqline(time_delta_disabled)
qqnorm(time_delta_enabled); qqline(time_delta_enabled)

t.test(x = time_delta_disabled, y = time_delta_enabled, alternative = "less")

print(fivenum(time_delta_enabled))

data.mean <- mean(time_delta_enabled)
data.sd <- sd(time_delta_enabled)
data.median <- median(time_delta_enabled)

mu <- mean(time_delta_disabled)
sd <- sd(time_delta_disabled)
median <- median(time_delta_disabled)
n <- 75
xbar <- data.mean
s <- data.sd
df <- n - 1

t <- (xbar - mu) / (s / sqrt(n))
print(pt(t, df, lower.tail = T))

wilcox.test(time_delta_disabled, time_delta_enabled, alternative = "less")
t.test(log(time_delta_disabled), log(time_delta_enabled), alternative = "less")

# Second hypothesis test: Is the accuracy for the test with thinking enabled greater than the test with thinking
# disabled?

successes <- c(63, 64)
totals <- c(75, 75)

prop.test(x = successes, n = totals, alternative = "greater", correct = TRUE)

