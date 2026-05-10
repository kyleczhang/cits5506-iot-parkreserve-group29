function SpotModal({
  spot,
  onClose,
  reserveSpot,
  cancelReservation
}) {

  if (!spot) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        backgroundColor: "rgba(0,0,0,0.5)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1000
      }}
    >

      <div
        style={{
          backgroundColor: "white",
          padding: "30px",
          borderRadius: "12px",
          width: "320px",
          textAlign: "center",
          boxShadow: "0 6px 14px rgba(0,0,0,0.2)"
        }}
      >

        <h2 style={{ marginBottom: "20px" }}>
          Spot {spot.id}
        </h2>

        <p>
          <strong>Status:</strong> {spot.status}
        </p>

        <p>
          <strong>Reservation Cost:</strong> $10
        </p>

        <p style={{ marginBottom: "25px", color: "gray" }}>
          Smart parking bay with live status tracking.
        </p>

        {/* Reserve Button */}
        {spot.status === "available" && (
          <button
            onClick={() => reserveSpot(spot.id)}
            style={{
              marginRight: "10px",
              padding: "10px 16px",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              backgroundColor: "#0077cc",
              color: "white",
              fontWeight: "bold"
            }}
          >
            Reserve
          </button>
        )}

        {/* Cancel Button */}
        {spot.status === "reserved" && (
          <button
            onClick={() => cancelReservation(spot.id)}
            style={{
              marginRight: "10px",
              padding: "10px 16px",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              backgroundColor: "#ffcc00",
              fontWeight: "bold"
            }}
          >
            Cancel
          </button>
        )}

        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            padding: "10px 16px",
            border: "none",
            borderRadius: "8px",
            cursor: "pointer",
            backgroundColor: "#ddd",
            fontWeight: "bold"
          }}
        >
          Close
        </button>

      </div>

    </div>
  );
}

export default SpotModal;