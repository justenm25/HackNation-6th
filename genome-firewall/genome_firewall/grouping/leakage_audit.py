from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from ..exceptions import LeakageError


def audit_split_homology(split_by_sample: Mapping[str, str], group_by_sample: Mapping[str, str]) -> dict:
    if set(split_by_sample) != set(group_by_sample):
        missing_groups = sorted(set(split_by_sample) - set(group_by_sample))
        extra_groups = sorted(set(group_by_sample) - set(split_by_sample))
        raise LeakageError(f"Split/group sample mismatch; missing_groups={missing_groups}, extra_groups={extra_groups}")
    partitions: dict[str, set[str]] = defaultdict(set)
    for sample, group in group_by_sample.items():
        partitions[group].add(split_by_sample[sample])
    crossing = {group: sorted(values) for group, values in partitions.items() if len(values) > 1}
    if crossing:
        raise LeakageError(f"Genetic groups cross protected partitions: {crossing}")
    return {
        "passed": True,
        "sample_count": len(split_by_sample),
        "group_count": len(partitions),
        "partition_counts": {name: list(split_by_sample.values()).count(name) for name in sorted(set(split_by_sample.values()))},
    }

