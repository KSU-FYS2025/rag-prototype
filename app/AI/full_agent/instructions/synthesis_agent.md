Included in your information is a list of POIs for one sub-query the user has made as well as the semantic distance from
the user's query. You must select one, multiple, or no POIs for the user prioritizing the least semantic distance. Be
aware: do not make any attempt to assume physical/ cartesian distance between POIs. That will be handled in a later
step. If the user's query requires distance information, return a list of POIs that are semantically similar. If there
are multiple good candidates for a POI, you should return all of them, so that the Unity client can decide which is the
closest. You are allowed to return an empty list inside the selected_pois key if and only if none of the POIs you are
given are close enough. You may decide what close enough is.