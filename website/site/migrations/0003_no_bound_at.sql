-- An ARN's first-run time isn't shown anywhere any more. Slots keep the order the ARNs were added (rowid).
ALTER TABLE arns DROP COLUMN bound_at;
