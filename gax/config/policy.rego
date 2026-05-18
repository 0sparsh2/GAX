package gax

default allow = false

allow {
  input.side_effects == "read"
  not denied_command
  not denied_repo
}

denied_command {
  input.command == "destructive.example"
}

denied_repo {
  some repo
  repo := input.args.repo
  input.claims.tenant_id == "restricted"
  repo != "allowed/repo"
}
