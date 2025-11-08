"""Example of Phase 2: Creation Burst with Coherence Analysis.

This shows how the basic creation_burst geist can evolve to use embeddings
to distinguish between coherent bursts (focused deep dives) and scattered
bursts (exploratory wandering).

NOT YET IMPLEMENTED - This is a design sketch.
"""

from typing import TYPE_CHECKING, List, Tuple

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> List[Suggestion]:
    """Find burst days and analyze their semantic coherence.

    Phase 2 enhancement: Not just "you created many notes," but
    "you created many notes about the same thing" (coherent) vs.
    "you created many notes about diverse topics" (scattered).
    """
    # Step 1: Find burst days (same as Phase 1)
    burst_days = _get_burst_days(vault, min_notes=5)

    if not burst_days:
        return []

    # Step 2: For each burst day, compute semantic coherence
    scored_bursts = []
    for day_date, note_titles in burst_days:
        notes = [vault.get_note_by_title(title) for title in note_titles if title]

        # Get current embeddings for those notes
        embeddings = []
        for note in notes:
            try:
                emb = vault.embedding(note)
                embeddings.append(emb)
            except Exception:
                continue

        if len(embeddings) < 2:
            continue

        # Compute pairwise similarity (coherence metric)
        coherence = _compute_cluster_coherence(embeddings)

        scored_bursts.append(
            {
                "date": day_date,
                "titles": note_titles,
                "count": len(note_titles),
                "coherence": coherence,
            }
        )

    if not scored_bursts:
        return []

    # Step 3: Pick most interesting burst
    # Prefer high-coherence (focused) or very-low-coherence (scattered) bursts
    # Medium coherence is less interesting
    burst = _pick_interesting_burst(vault, scored_bursts)

    # Step 4: Generate provocation based on coherence pattern
    return [_generate_coherence_provocation(burst)]


def _get_burst_days(
    vault: "VaultContext", min_notes: int = 5
) -> List[Tuple[str, List[str]]]:
    """Get list of (date, note_titles) for days with min_notes+ created."""
    cursor = vault.db.execute(
        """
        SELECT DATE(created) as creation_date,
               GROUP_CONCAT(title, '|') as note_titles
        FROM notes
        WHERE NOT path LIKE 'geist journal/%'
        GROUP BY DATE(created)
        HAVING COUNT(*) >= ?
        ORDER BY COUNT(*) DESC
        """,
        (min_notes,),
    )

    results = []
    for row in cursor.fetchall():
        date_str, titles_str = row
        titles = titles_str.split("|") if titles_str else []
        results.append((date_str, titles))

    return results


def _compute_cluster_coherence(embeddings: List[npt.NDArray[np.float32]]) -> float:
    """Compute average pairwise cosine similarity.

    Returns:
        Float between 0 (scattered) and 1 (tightly clustered)
    """
    if len(embeddings) < 2:
        return 1.0

    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

    # Convert to numpy array
    emb_matrix = np.array(embeddings)

    # Compute pairwise similarities
    similarity_matrix = cosine_similarity(emb_matrix)

    # Get upper triangle (excluding diagonal)
    triu_indices = np.triu_indices_from(similarity_matrix, k=1)
    similarities = similarity_matrix[triu_indices]

    # Return mean similarity
    return float(np.mean(similarities))


def _pick_interesting_burst(vault: "VaultContext", scored_bursts: List[dict]) -> dict:
    """Pick the most interesting burst to highlight.

    Prefers:
    1. Very coherent bursts (focused deep dives)
    2. Very scattered bursts (exploratory wandering)
    3. Skips medium coherence (less interesting)
    """
    # Categorize bursts
    coherent = [b for b in scored_bursts if b["coherence"] > 0.7]
    scattered = [b for b in scored_bursts if b["coherence"] < 0.4]

    # Prefer extreme cases
    if coherent:
        # Pick most coherent
        return max(coherent, key=lambda b: b["coherence"])
    elif scattered:
        # Pick most scattered
        return min(scattered, key=lambda b: b["coherence"])
    else:
        # Fallback to random if all medium coherence
        return vault.sample(scored_bursts, k=1)[0]


def _generate_coherence_provocation(burst: dict) -> Suggestion:
    """Generate suggestion text based on burst coherence."""
    date = burst["date"]
    titles = burst["titles"]
    count = burst["count"]
    coherence = burst["coherence"]

    # Limit displayed titles
    display_titles = titles[:6]
    title_list = ", ".join([f"[[{t}]]" for t in display_titles])
    if len(titles) > 6:
        title_list += f", and {len(titles) - 6} more"

    if coherence > 0.75:
        # Highly coherent burst
        text = (
            f"On {date}, you created {count} notes that all cluster tightly around "
            f"a single theme (coherence: {coherence:.2f}). Was this a deep dive day? "
            f"{title_list}"
        )
    elif coherence < 0.35:
        # Highly scattered burst
        text = (
            f"On {date}, you created {count} notes about completely different topics "
            f"(coherence: {coherence:.2f}). Exploratory wandering or intellectual chaos? "
            f"{title_list}"
        )
    elif 0.5 < coherence < 0.7:
        # Medium-high coherence (somewhat related)
        text = (
            f"On {date}, you created {count} notes that are loosely related "
            f"(coherence: {coherence:.2f}). Were you circling around an idea? "
            f"{title_list}"
        )
    else:
        # Medium coherence (mixed)
        text = (
            f"On {date}, you created {count} notes with mixed coherence "
            f"(coherence: {coherence:.2f}). Some clustering, some wandering. "
            f"{title_list}"
        )

    return Suggestion(
        text=text,
        notes=titles,
        geist_id="creation_burst",
    )


# ============================================================================
# PHASE 3: Temporal Trajectory Analysis
# ============================================================================


def suggest_with_trajectory(vault: "VaultContext") -> List[Suggestion]:
    """Track how burst-day note clusters evolve over time.

    Phase 3 enhancement: Did burst notes:
    - Converge (started diverse, became coherent)?
    - Diverge (started related, drifted apart)?
    - Remain stable (coherence unchanged)?
    """
    # Step 1: Find burst days with sufficient session history
    burst_days = _get_burst_days_with_history(vault, min_notes=5, min_sessions=5)

    if not burst_days:
        return []

    # Step 2: For each burst day, compute coherence trajectory
    trajectories = []
    for day_date, note_paths in burst_days:
        # Get all sessions since burst day
        sessions = _get_sessions_since_date(vault, day_date)

        if len(sessions) < 5:
            continue

        # Track coherence across sessions
        coherence_over_time = []
        for session_id in sessions:
            embeddings = _get_embeddings_for_session(vault, note_paths, session_id)

            if len(embeddings) >= 2:
                coherence = _compute_cluster_coherence(embeddings)
                coherence_over_time.append(coherence)

        if len(coherence_over_time) < 3:
            continue

        # Classify trajectory pattern
        pattern = _classify_trajectory(coherence_over_time)

        trajectories.append(
            {
                "date": day_date,
                "paths": note_paths,
                "coherence_history": coherence_over_time,
                "pattern": pattern,
            }
        )

    if not trajectories:
        return []

    # Pick most interesting trajectory
    trajectory = vault.sample(trajectories, k=1)[0]

    return [_generate_trajectory_provocation(vault, trajectory)]


def _classify_trajectory(coherence_over_time: List[float]) -> str:
    """Classify how coherence changed over time."""
    if len(coherence_over_time) < 3:
        return "stable"

    # Compare first third to last third
    first_third = coherence_over_time[: len(coherence_over_time) // 3]
    last_third = coherence_over_time[-len(coherence_over_time) // 3 :]

    first_mean = np.mean(first_third)
    last_mean = np.mean(last_third)
    delta = last_mean - first_mean
    volatility = np.std(coherence_over_time)

    if volatility > 0.15:
        return "volatile"
    elif delta > 0.15:
        return "convergent"
    elif delta < -0.15:
        return "divergent"
    else:
        return "stable"


def _generate_trajectory_provocation(vault: "VaultContext", trajectory: dict) -> Suggestion:
    """Generate provocation based on coherence trajectory."""
    date = trajectory["date"]
    pattern = trajectory["pattern"]
    coherence_history = trajectory["coherence_history"]

    # Get note titles
    titles = [vault.get_note(path).title for path in trajectory["paths"]]
    display_titles = ", ".join([f"[[{t}]]" for t in titles[:5]])
    if len(titles) > 5:
        display_titles += f", and {len(titles) - 5} more"

    initial_coherence = coherence_history[0]
    final_coherence = coherence_history[-1]
    num_sessions = len(coherence_history)

    if pattern == "convergent":
        text = (
            f"On {date}, you created {len(titles)} diverse notes "
            f"(coherence: {initial_coherence:.2f}), but over the next {num_sessions} sessions "
            f"they've converged into a tight cluster (now: {final_coherence:.2f}). "
            f"You were exploring the edges of an idea that's now crystallizing. "
            f"{display_titles}"
        )
    elif pattern == "divergent":
        text = (
            f"On {date}, you created {len(titles)} tightly related notes "
            f"(coherence: {initial_coherence:.2f}), but they've drifted apart over time "
            f"(now: {final_coherence:.2f}). Same topic, but your understanding has "
            f"fragmented—losing the thread or discovering nuance? {display_titles}"
        )
    elif pattern == "stable":
        text = (
            f"On {date}, you created {len(titles)} notes that formed a cluster "
            f"and have stayed that way for {num_sessions} sessions. Foundational day? "
            f"{display_titles}"
        )
    else:  # volatile
        text = (
            f"On {date}, you created {len(titles)} notes whose coherence keeps changing—"
            f"sometimes clustered, sometimes scattered. Are these notes still searching "
            f"for their relationship to each other? {display_titles}"
        )

    return Suggestion(
        text=text,
        notes=titles,
        geist_id="creation_burst",
    )


# Helper functions for Phase 3 (session history access)


def _get_burst_days_with_history(
    vault: "VaultContext", min_notes: int, min_sessions: int
) -> List[Tuple[str, List[str]]]:
    """Get burst days that have sufficient session history."""
    # Implementation would query sessions table and filter burst days
    # to those with at least min_sessions of embedding history
    raise NotImplementedError("Requires session_embeddings implementation")


def _get_sessions_since_date(vault: "VaultContext", date_str: str) -> List[int]:
    """Get session IDs for all sessions since given date."""
    raise NotImplementedError("Requires sessions table implementation")


def _get_embeddings_for_session(
    vault: "VaultContext", note_paths: List[str], session_id: int
) -> List[npt.NDArray[np.float32]]:
    """Get embeddings for given notes from specific session."""
    raise NotImplementedError("Requires session_embeddings table implementation")
