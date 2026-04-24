# Reservation Workflow and Check-In Design

## Reservation Time and Arrival Policy

Users may reserve a parking bay by selecting an expected arrival time. However, reservations can only be made up to one hour in advance. In other words, the user may only choose an arrival time within the next hour. We consider this window sufficient for most users in Perth, while also helping the system avoid unnecessarily long reservation holds.

Users are allowed to arrive earlier than their selected arrival time. However, if a user has not checked in by the reserved arrival time plus a five-minute grace period, the system will automatically release the bay. At that point, the barrier will be lowered and the indicator light will return to green, showing that the bay is available for others to use.

## Cancellation and Breach Policy

The system will also record user breaches. If a user fails to check in before the end of the grace period, this will count as one breach. If a user accumulates more than two breaches within a single month, that user will be temporarily banned from using the parking reservation function.

If a user cancels a reservation within 30 minutes of making it, the cancellation will not be treated as a breach. However, if the user cancels more than 30 minutes after making the reservation, it will count as one breach. This policy is intended to discourage users from holding bays unnecessarily while still allowing reasonable flexibility when plans change.

## Check-In Design Options

The ideal check-in method would be automatic license plate recognition. This would allow the system to identify the reserved vehicle automatically without requiring additional user action. However, this approach introduces several practical challenges.

If the camera is installed at the car park entrance, the user would be checked in as soon as the vehicle enters the car park. In that case, the reserved bay would be released immediately, and there would be a risk that another driver could occupy the bay before the reserved user actually reaches it.

To avoid this issue, the camera would need to be installed near each parking bay rather than at the entrance. However, this creates further difficulties. Parking structures often have complex layouts and poor lighting conditions, which can reduce the reliability of plate recognition. In addition, installing one camera for each parking bay would be costly and impractical for our prototype.

## Current Chosen Approach and Limitation

Our current plan is therefore not to implement automatic identity recognition. Instead, check-in will be defined as a user confirmation action on the dashboard. This is a simpler and more feasible approach for the current project scope, although it is less intelligent than an automated identification system.

We recognize that this is a limitation of the current prototype. While the system will still demonstrate reservation control, state transitions, and physical barrier actuation, it will not verify automatically that the arriving vehicle is the same one that made the reservation. Automatic identity verification can be considered as future work for a more advanced version of the system.
