# `tingle check --json` → the sticky comment's markdown. $marker opens the
# body, so the next run finds this comment and edits it.
def signed: if . == null then "" elif . > 0 then "+\(.)" else "\(.)" end;
def changed: .error != null or (.net // 0) != 0
  or (.added // 0) != 0 or (.removed // 0) != 0;
# a comment holds at most 65536 characters; past this the list is cut
def limit_shown: 200;

.check as $check
| [.metrics[] | select(.name as $name | $check.worsened | index($name))
   | .name as $name | .added_occurrences[]
   | "- `\($name)` `\(.file)\(if .line then ":\(.line)" else "" end)`"
     + (if .note then " \(.note)" else "" end)] as $added
| [.metrics[] | select(changed)] as $rows
| (if $check.judged == 1 then "metric" else "metrics" end) as $noun
| [
    $marker,
    "### tingle",
    "",
    (if $check.failed then
       "❌ check failed against `\(.base)`: "
       + if $check.policy == "sum" then
           "metrics grew by a net +\($check.net_total) (policy: sum)"
         else
           "\($check.worsened | join(", ")) grew (policy: any)"
         end
     else
       (if $check.net_total < 0 then
          "🎉 no new debt, and \(-$check.net_total) paid off"
        else
          "🎉 no new debt"
        end) + ": \($check.judged) \($noun) against `\(.base)`"
     end),
    "",
    (if $rows == [] then "No metric changed."
     else
       "| Metric | Added | Removed | Net | Total |",
       "| --- | ---: | ---: | ---: | ---: |",
       ($rows[] | if .error then "| \(.name) | | | error | |"
        else "| \(.name) | \(.added | signed) | \(.removed // "")"
             + " | \(.net | signed) | \(.total // "") |"
        end)
     end),
    (if $added == [] then empty
     else
       "",
       "<details><summary>Added (\($added | length))</summary>",
       "",
       $added[:limit_shown][],
       (if ($added | length) > limit_shown
        then "- …and \(($added | length) - limit_shown) more" else empty end),
       "",
       "</details>"
     end)
  ]
| join("\n")
