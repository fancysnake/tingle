# `tingle check --json` → one workflow command per occurrence a worsened
# metric added. $prefix is the config root relative to the workspace, since
# occurrence paths are relative to the root and annotations to the repo.
def prop: gsub("%"; "%25") | gsub("\r"; "%0D") | gsub("\n"; "%0A")
  | gsub(":"; "%3A") | gsub(","; "%2C");
def msg: gsub("%"; "%25") | gsub("\r"; "%0D") | gsub("\n"; "%0A");

(if .check.failed then "error" else "warning" end) as $level
| .check.worsened as $worsened
| .metrics[]
| select(.name as $name | $worsened | index($name))
| .name as $name
| .added_occurrences[]
| (if $prefix == "." then .file else "\($prefix)/\(.file)" end) as $file
| "::\($level) file=\($file | prop)"
  + (if .line then ",line=\(.line)" else "" end)
  + ",title=\("tingle: \($name)" | prop)"
  + "::\("\($name) +1" + (if .note then ": \(.note)" else "" end) | msg)"
