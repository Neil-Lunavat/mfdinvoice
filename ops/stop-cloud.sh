#!/usr/bin/env bash
# Stop everything the old cloud server costs money for, without deleting anything: the database is switched off
# (its data stays), the two daily wake-up jobs are paused, and both Cloud Run services stop taking public traffic.
#
#   bash ops/stop-cloud.sh          # stop
#   bash ops/stop-cloud.sh start    # put it all back
set -uo pipefail
cd "$(dirname "$0")/.."
G="bash ops/gcloud.sh"; P="${PROJECT:-harekrishna-509820}"; R=asia-south1
if [[ "${1:-stop}" == start ]]; then POLICY=ALWAYS; JOBS=resume; INGRESS=all; else POLICY=NEVER; JOBS=pause; INGRESS=internal; fi

for j in brain-chores-production brain-chores-staging; do
  $G scheduler jobs $JOBS "$j" --project "$P" --location "$R" --quiet
done
for s in brain brain-staging; do
  $G run services update "$s" --project "$P" --region "$R" --ingress "$INGRESS" --quiet
done
$G sql instances patch brain-db --project "$P" --activation-policy "$POLICY" --quiet

echo; echo "== now =="
$G scheduler jobs list --project "$P" --location "$R" --format="table(name.basename(),state)"
$G run services list --project "$P" --region "$R" --format="table(metadata.name,metadata.annotations['run.googleapis.com/ingress'])"
$G sql instances list --project "$P" --format="table(name,state,settings.activationPolicy)"
