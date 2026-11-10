# the ids on one page of issue comments that carry the marker and that the
# token wrote: a participant's comment carrying the marker is not ours to edit
.[] | select(.body | startswith(env.MARKER))
| select(.user.id == (env.TOKEN_USER_ID | tonumber)) | .id
