import pandas as pd
import numpy as np
from itertools import combinations
from collections import defaultdict
from typing import Dict, List

"""
Multi-Touch Attribution (MTA) Model for Paid Channels
======================================================
Implements 4 attribution models for B2B marketing analysis:
1. First Touch
2. Last Touch 
3. Linear (equal credit)
4. Position-Based (U-shaped: 40% first, 40% last, 20% middle)
5. Time Decay (exponential decay toward conversion)
6. Markov Chain (data-driven)

Usage:
    df = pd.read_csv('touchpoints.csv')  # columns: customer_id, channel, timestamp, converted
    attr = AttributionModel(df)
    results = attr.compare_all_models()
    print(results)
"""


class AttributionModel:
    """
    Multi-touch attribution for B2B paid channel analysis.
    
    Input DataFrame columns:
    - customer_id: unique customer/deal identifier
    - channel: marketing channel (e.g., 'Google Search', 'LinkedIn', 'Email')
    - timestamp: datetime of touchpoint
    - converted: boolean, True if this customer eventually converted
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.df = self.df.sort_values(['customer_id', 'timestamp'])
        self.channels = self.df['channel'].unique().tolist()
        self._paths = self._build_paths()

    def _build_paths(self) -> Dict:
        """Build touchpoint paths for each converting customer."""
        paths = {}
        converted_customers = self.df[self.df['converted'] == True]['customer_id'].unique()
        
        for cid in converted_customers:
            customer_touches = self.df[self.df['customer_id'] == cid].sort_values('timestamp')
            paths[cid] = customer_touches['channel'].tolist()
        
        return paths

    def first_touch(self) -> pd.Series:
        """100% credit to the first touchpoint."""
        credits = defaultdict(float)
        for path in self._paths.values():
            if path:
                credits[path[0]] += 1.0
        return pd.Series(credits, name='first_touch')

    def last_touch(self) -> pd.Series:
        """100% credit to the last touchpoint."""
        credits = defaultdict(float)
        for path in self._paths.values():
            if path:
                credits[path[-1]] += 1.0
        return pd.Series(credits, name='last_touch')

    def linear(self) -> pd.Series:
        """Equal credit distributed across all touchpoints."""
        credits = defaultdict(float)
        for path in self._paths.values():
            if path:
                weight = 1.0 / len(path)
                for channel in path:
                    credits[channel] += weight
        return pd.Series(credits, name='linear')

    def position_based(self, first_weight=0.4, last_weight=0.4) -> pd.Series:
        """
        U-shaped model: 40% first, 40% last, 20% split among middle.
        Adjustable weights via parameters.
        """
        middle_weight = 1.0 - first_weight - last_weight
        credits = defaultdict(float)

        for path in self._paths.values():
            n = len(path)
            if n == 1:
                credits[path[0]] += 1.0
            elif n == 2:
                credits[path[0]] += first_weight + middle_weight / 2
                credits[path[-1]] += last_weight + middle_weight / 2
            else:
                credits[path[0]] += first_weight
                credits[path[-1]] += last_weight
                middle_channels = path[1:-1]
                if middle_channels:
                    per_middle = middle_weight / len(middle_channels)
                    for ch in middle_channels:
                        credits[ch] += per_middle

        return pd.Series(credits, name='position_based')

    def time_decay(self, half_life_days: float = 7.0) -> pd.Series:
        """
        Exponential time decay: touchpoints closer to conversion get more credit.
        half_life_days: number of days for credit to halve.
        """
        credits = defaultdict(float)

        for cid, path in self._paths.items():
            customer_touches = self.df[
                (self.df['customer_id'] == cid) & (self.df['converted'] == True)
            ].sort_values('timestamp')

            if len(customer_touches) == 0:
                continue

            conversion_date = customer_touches['timestamp'].max()
            weights = []

            for _, row in customer_touches.iterrows():
                days_before = (conversion_date - row['timestamp']).days
                weight = 2 ** (-days_before / half_life_days)
                weights.append((row['channel'], weight))

            total_weight = sum(w for _, w in weights)
            for channel, weight in weights:
                credits[channel] += weight / total_weight

        return pd.Series(credits, name='time_decay')

    def markov_chain(self) -> pd.Series:
        """
        Data-driven Markov Chain attribution.
        Calculates removal effect: how much does conversion probability 
        drop when each channel is removed from the path?
        """
        # Build all paths including non-converters
        all_paths = defaultdict(lambda: {'conversions': 0, 'total': 0})

        for cid in self.df['customer_id'].unique():
            customer = self.df[self.df['customer_id'] == cid].sort_values('timestamp')
            path = tuple(customer['channel'].tolist())
            converted = customer['converted'].any()
            all_paths[path]['total'] += 1
            if converted:
                all_paths[path]['conversions'] += 1

        # Calculate baseline conversion rate
        total_conversions = sum(v['conversions'] for v in all_paths.values())
        total_customers = len(self.df['customer_id'].unique())
        baseline_rate = total_conversions / max(total_customers, 1)

        # Calculate removal effect for each channel
        removal_effects = {}
        for channel in self.channels:
            # Remove all paths containing this channel
            remaining_conversions = sum(
                v['conversions'] for path, v in all_paths.items()
                if channel not in path
            )
            remaining_customers = sum(
                v['total'] for path, v in all_paths.items()
                if channel not in path
            )
            rate_without = remaining_conversions / max(remaining_customers, 1)
            removal_effects[channel] = max(baseline_rate - rate_without, 0)

        # Normalize to sum to total conversions
        total_effect = sum(removal_effects.values())
        if total_effect > 0:
            credits = {
                ch: (effect / total_effect) * total_conversions
                for ch, effect in removal_effects.items()
            }
        else:
            credits = {ch: 0 for ch in self.channels}

        return pd.Series(credits, name='markov_chain')

    def compare_all_models(self) -> pd.DataFrame:
        """
        Run all 6 attribution models and return comparison DataFrame.
        Normalized to show % of conversions attributed to each channel.
        """
        models = {
            'first_touch': self.first_touch(),
            'last_touch': self.last_touch(),
            'linear': self.linear(),
            'position_based': self.position_based(),
            'time_decay': self.time_decay(),
            'markov_chain': self.markov_chain(),
        }

        result = pd.DataFrame(models).fillna(0)
        result.index.name = 'channel'

        # Normalize each model to percentages
        for col in result.columns:
            total = result[col].sum()
            if total > 0:
                result[col] = (result[col] / total * 100).round(1)

        return result.sort_values('markov_chain', ascending=False)

    def budget_recommendation(self, total_budget: float) -> pd.DataFrame:
        """
        Recommend budget allocation based on Markov Chain attribution.
        Assumes proportional budget allocation by attributed conversions.
        """
        markov = self.markov_chain()
        total = markov.sum()

        if total == 0:
            return pd.DataFrame()

        recommendation = pd.DataFrame({
            'channel': markov.index,
            'attributed_conversions': markov.values.round(1),
            'attribution_share_pct': (markov.values / total * 100).round(1),
            'recommended_budget': (markov.values / total * total_budget).round(0)
        }).sort_values('recommended_budget', ascending=False)

        return recommendation


if __name__ == '__main__':
    # Synthetic B2B touchpoint data
    np.random.seed(42)
    channels = ['Google Search', 'LinkedIn', 'Content/SEO', 'Email', 'Webinar', 'Outbound']
    n_customers = 300

    records = []
    for i in range(n_customers):
        cid = f'DEAL{i:04d}'
        n_touches = np.random.randint(1, 8)
        converted = np.random.random() < 0.25
        base_date = pd.Timestamp('2024-01-01') + pd.Timedelta(days=np.random.randint(0, 300))

        # First touch often Google or LinkedIn
        first_channel = np.random.choice(channels[:3], p=[0.4, 0.35, 0.25])
        touch_channels = [first_channel]

        for j in range(1, n_touches):
            touch_channels.append(np.random.choice(channels))

        for j, ch in enumerate(touch_channels):
            records.append({
                'customer_id': cid,
                'channel': ch,
                'timestamp': base_date + pd.Timedelta(days=j * np.random.randint(2, 15)),
                'converted': converted
            })

    df = pd.DataFrame(records)

    print("Multi-Touch Attribution Analysis")
    print(f"Dataset: {df['customer_id'].nunique()} customers, "
          f"{df['converted'].any() if False else df.groupby('customer_id')['converted'].any().sum()} conversions\n")

    attr = AttributionModel(df)

    print("=== Attribution Model Comparison (% of conversions) ===")
    comparison = attr.compare_all_models()
    print(comparison.to_string())

    print("\n=== Budget Recommendation (based on $100K monthly budget) ===")
    budget = attr.budget_recommendation(total_budget=100000)
    print(budget.to_string(index=False))
