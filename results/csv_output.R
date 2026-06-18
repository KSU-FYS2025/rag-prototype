library(rjson)

# ---------------------------------------------------------------------------
# FILE PATHS — update these to match your actual file locations
# ---------------------------------------------------------------------------

eval_set_path  <- "results/full_agent_full_agent_eval_set_large_5_1781790075.9050326.json"
poi_path       <- "UpdatedFloorsAndFireinteraction_POIs.json"
output_path    <- "eval_results_with_pois.csv"

# ---------------------------------------------------------------------------
# Sanity-check paths before doing any work
# ---------------------------------------------------------------------------

if (!file.exists(eval_set_path)) stop("Eval set file not found: ", eval_set_path)
if (!file.exists(poi_path))      stop("POI file not found: ", poi_path)

cat("Working directory:", getwd(), "\n")
cat("Loading eval set from:", normalizePath(eval_set_path), "\n")
cat("Loading POI data from:", normalizePath(poi_path), "\n")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

eval_set <- fromJSON(file = eval_set_path)
poi_data <- fromJSON(file = poi_path)

cat("Eval cases found:", length(eval_set$evalCaseResults), "\n")
cat("POIs found:", length(poi_data$pois), "\n")

# ---------------------------------------------------------------------------
# Build POI lookup: identification (as string) -> name
# ---------------------------------------------------------------------------

poi_lookup <- setNames(
  sapply(poi_data$pois, function(p) p$name),
  sapply(poi_data$pois, function(p) as.character(p$identification))
)

# ---------------------------------------------------------------------------
# Helper: extract all POI IDs referenced across all actions in one invocation
#
# IDs appear in different fields depending on the action cmd:
#   navigation      -> action$id              (scalar)
#   resolve_nearest -> action$candidate_ids   (list)
#   clarify         -> action$suggestions[[i]]$id  (list of objects)
#   answer          -> action$source_ids      (list)
# ---------------------------------------------------------------------------

extract_ids_from_actions <- function(actions) {
  ids <- c()
  for (action in actions) {
    cmd <- action$cmd
    if (!is.null(cmd)) {
      if (cmd == "navigation" && !is.null(action$id)) {
        ids <- c(ids, as.integer(action$id))
      } else if (cmd == "resolve_nearest" && !is.null(action$candidate_ids)) {
        ids <- c(ids, as.integer(unlist(action$candidate_ids)))
      } else if (cmd == "clarify" && !is.null(action$suggestions)) {
        ids <- c(ids, as.integer(sapply(action$suggestions, function(s) s$id)))
      } else if (cmd == "answer" && !is.null(action$source_ids)) {
        ids <- c(ids, as.integer(unlist(action$source_ids)))
      }
    }
  }
  unique(ids)
}

# ---------------------------------------------------------------------------
# Iterate over eval cases and build output rows
# ---------------------------------------------------------------------------

rows <- list()

for (eval_case in eval_set$evalCaseResults) {

  # Final response is a JSON string embedded as plain text — must be parsed
  final_response_raw <- tryCatch(
    eval_case$evalMetricResultPerInvocation[[1]]$actualInvocation$finalResponse$parts[[1]]$text,
    error = function(e) NA_character_
  )

  user_query <- tryCatch(
    eval_case$evalMetricResultPerInvocation[[1]]$actualInvocation$userContent$parts[[1]]$text,
    error = function(e) NA_character_
  )

  parsed_response <- tryCatch(
    fromJSON(json_str = final_response_raw),
    error = function(e) {
      warning("Could not parse final_response JSON for query '", user_query, "': ", conditionMessage(e))
      NULL
    }
  )

  # If the response couldn't be parsed, still write the raw text with NA POI columns
  if (is.null(parsed_response)) {
    rows[[length(rows) + 1]] <- data.frame(
      user_query      = user_query,
      system_response = final_response_raw,
      poi_ids         = NA_character_,
      poi_names       = NA_character_,
      stringsAsFactors = FALSE
    )
    next
  }

  system_response_text <- parsed_response$response
  actions  <- if (!is.null(parsed_response$actions)) parsed_response$actions else list()
  poi_ids  <- extract_ids_from_actions(actions)

  if (length(poi_ids) > 0) {
    poi_names     <- sapply(as.character(poi_ids), function(id) {
      name <- poi_lookup[id]
      if (is.na(name)) paste0("Unknown (id=", id, ")") else name
    })
    poi_ids_str   <- paste(poi_ids,   collapse = "; ")
    poi_names_str <- paste(poi_names, collapse = "; ")
  } else {
    poi_ids_str   <- NA_character_
    poi_names_str <- NA_character_
  }

  rows[[length(rows) + 1]] <- data.frame(
    user_query      = user_query,
    system_response = system_response_text,
    poi_ids         = poi_ids_str,
    poi_names       = poi_names_str,
    stringsAsFactors = FALSE
  )

}

# ---------------------------------------------------------------------------
# Combine and write CSV
# ---------------------------------------------------------------------------

output_df <- do.call(rbind, rows)

write.csv(output_df, file = output_path, row.names = FALSE)

cat("Done. Written", nrow(output_df), "rows to:", normalizePath(output_path), "\n")