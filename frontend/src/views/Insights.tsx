import { Navigate } from "react-router-dom";

/** Insights folded into the dashboard: the explanation tally lives there now, and the cross-learner
 * loss map is a team tool (/team/lossmap/:lectureId). Old links land on the dashboard. */
export default function Insights() {
  return <Navigate to="/" replace />;
}
