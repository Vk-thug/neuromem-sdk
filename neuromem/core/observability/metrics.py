"""
Metrics collection for observability.
"""

from collections import defaultdict
from typing import Dict
import statistics


class MetricsCollector:
    """Collects and aggregates metrics"""
    
    def __init__(self):
        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)
        self.gauges = {}
    
    def increment(self, metric: str, tags: Dict[str, str] = None):
        """Increment a counter"""
        key = self._make_key(metric, tags)
        self.counters[key] += 1
    
    def record(self, metric: str, value: float, tags: Dict[str, str] = None):
        """Record a value in histogram"""
        key = self._make_key(metric, tags)
        self.histograms[key].append(value)
    
    def gauge(self, metric: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge value"""
        key = self._make_key(metric, tags)
        self.gauges[key] = value
    
    def get_counter(self, metric: str, tags: Dict[str, str] = None) -> int:
        """Get counter value"""
        key = self._make_key(metric, tags)
        return self.counters.get(key, 0)
    
    def get_percentile(self, metric: str, percentile: int, tags: Dict[str, str] = None) -> float:
        """Get percentile from histogram"""
        key = self._make_key(metric, tags)
        values = self.histograms.get(key, [])
        if not values:
            return 0.0
        return statistics.quantiles(values, n=100)[percentile - 1] if len(values) > 1 else values[0]
    
    def get_avg(self, metric: str, tags: Dict[str, str] = None) -> float:
        """Get average from histogram"""
        key = self._make_key(metric, tags)
        values = self.histograms.get(key, [])
        return statistics.mean(values) if values else 0.0
    
    def get_all_metrics(self) -> Dict:
        """Get all metrics as dict"""
        return {
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'histograms': {
                k: {
                    'count': len(v),
                    'avg': statistics.mean(v) if v else 0,
                    'p95': statistics.quantiles(v, n=100)[94] if len(v) > 1 else (v[0] if v else 0)
                }
                for k, v in self.histograms.items()
            }
        }
    
    def _make_key(self, metric: str, tags: Dict[str, str] = None) -> str:
        """Create metric key with tags"""
        if not tags:
            return metric
        tag_str = ','.join(f'{k}={v}' for k, v in sorted(tags.items()))
        return f'{metric}{{{tag_str}}}'
    
    def reset(self):
        """Reset all metrics"""
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()
