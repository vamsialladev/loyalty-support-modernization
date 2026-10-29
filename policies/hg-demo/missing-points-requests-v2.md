---
policy_id: missing-points-requests
title: Guest Rewards — Missing Points Requests
customer: hg-demo
version: 2
effective_from: 2026-07-01
effective_to: null
status: published
supersedes: 1
sections: ["1", "2", "3", "4.1", "4.2", "5", "5.1", "6", "7", "7.1", "7.2", "7.3"]
rules:
  waiting_period_days: 14
  claim_window_months: 12
  eligible_channels: [direct, phone]
  ota_eligible_with_member_on_booking: true
  corporate_rate_prefix: CORP
  pending_posting_blocks_adjustment: true
  supervisor_approval_required: true
  supervisor_limit_points: 20000
  business_date_timezone: America/New_York
synthetic: true
---
# Guest Rewards — Missing Points Requests (version 2)

> SYNTHETIC. Fictional policy. Applies to stays whose checkout date (Eastern time) is on or after 2026-07-01.

## 1. Purpose
How support agents handle a member's request for points they believe are missing from a completed stay.

## 2. Which version applies
Use the version of this policy in force on the stay's checkout date, in the property's local time (Eastern). Stays
that checked out before 2026-07-01 follow version 1.

## 3. Timing
A member may claim missing points no earlier than **14 days** after checkout, and no later than **12 months** after
checkout. Before 14 days, tell the member the date from which they can claim. After 12 months, the claim is declined.

## 4.1 Booking channels
Stays booked directly (hotel website, app, front desk) or by phone earn points.

## 4.2 Online travel agency bookings
Stays booked through an online travel agency earn points **when the member number was on the reservation at the time
of booking**. Adding a member number after booking does not qualify.

## 5. Already credited
If the ledger already shows the points for the stay, no adjustment is made. Show the member the posting. A reversal
followed by a re-post counts as credited at the re-posted amount.

## 5.1 Pending postings
If a posting for the stay is pending in the posting queue, do not adjust. Tell the member the expected posting date.

## 6. Approval
Every adjustment needs a supervisor's approval, and the person who proposed it cannot approve it. A supervisor may
approve up to 20,000 points per case; above that, escalate to the loyalty manager.

## 7. Escalation
If the stay record is missing or records disagree, escalate to the property for confirmation. Do not adjust on the
member's documents alone.

## 7.1 Duplicate profiles
If the points were credited to another profile belonging to the same member (confirmed on two identifiers), do not
adjust; refer the profiles to the data owner for a merge.

## 7.2 Merged member numbers
Stays booked under a member number that was merged into another account are credited to the account it was merged
into.

## 7.3 Corporate travel program
Travel-agent bookings normally earn no points. Exception: bookings made under the corporate travel program, shown by a
rate code starting with `CORP`, earn points as if booked directly.
