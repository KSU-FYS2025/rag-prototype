library(rjson)
json_data_disabled <- fromJSON(file = "results/evalset_results/full_agent_full_agent_eval_set_large_10_disabled_1782415557.690652.json")
json_data_enabled <- fromJSON(file = "results/evalset_results/full_agent_full_agent_eval_set_large_10_enabled_1782416910.1893363.json")

queries_disabled <- json_data_disabled$evalCaseResults
queries_enabled <- json_data_enabled$evalCaseResults

get_timestamps <- function(query) {
  timestamps <- sapply(query$sessionDetails$events, function(e) e$timestamp)
  timestamps[length(timestamps)] - timestamps[1]
}

time_delta_disabled <- sapply(queries_disabled, get_timestamps)
time_delta_enabled <- sapply(queries_enabled, get_timestamps)

print(fivenum(time_delta_enabled))

data.mean <- mean(time_delta_enabled)
data.sd <- sd(time_delta_enabled)

mu <- mean(time_delta_disabled)
n <- 75
xbar <- data.mean
s <- data.sd
df <- n - 1

t <- (xbar-mu)/(s/sqrt(n))
print(pt(t, df, lower.tail=T))