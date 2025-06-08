# tests/gp_core/test_selection_strategies.py
import pytest
import random
from typing import List, Tuple, Dict, Any
from unittest.mock import patch

from app.core.gp_algo import (
    Node,
    copy_tree, # Needed by selection functions
    tournament_selection,   # DEV-050
    roulette_wheel_selection # DEV-050
)

# --- Sample Population with Fitness for Testing ---
# (Node, fitness_score)
# We use simple Node("value") for individuals for ease of assertion.
# In reality, these would be more complex tree structures.
SAMPLE_POPULATION_FITNESS: List[Tuple[Node, float]] = [
    (Node("alpha1_best"), 1.0),
    (Node("alpha2_good"), 0.8),
    (Node("alpha3_mid"),  0.5),
    (Node("alpha4_poor"), 0.2),
    (Node("alpha5_worst"),0.1)
]

SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER: List[Tuple[Node, float]] = [
    (Node("alpha1_best_low"), 0.1), # Best
    (Node("alpha2_good_low"), 0.2),
    (Node("alpha3_mid_low"),  0.5),
    (Node("alpha4_poor_low"), 0.8),
    (Node("alpha5_worst_low"),1.0)  # Worst
]

# --- tournament_selection Tests ---
def test_tournament_selection_basic():
    """测试锦标赛选择基本功能。"""
    selected = tournament_selection(SAMPLE_POPULATION_FITNESS, num_selections=2, tournament_size=2, higher_fitness_is_better=True)
    assert len(selected) == 2
    for individual in selected:
        assert isinstance(individual, Node) # Should be copies

def test_tournament_selection_all_selected():
    """测试当选择数量等于或大于种群数量时。"""
    selected = tournament_selection(SAMPLE_POPULATION_FITNESS, num_selections=len(SAMPLE_POPULATION_FITNESS), tournament_size=2)
    assert len(selected) == len(SAMPLE_POPULATION_FITNESS)

    selected_more = tournament_selection(SAMPLE_POPULATION_FITNESS, num_selections=len(SAMPLE_POPULATION_FITNESS) + 2, tournament_size=2)
    assert len(selected_more) == len(SAMPLE_POPULATION_FITNESS) + 2 # Tournament selection selects with replacement implicitly by running multiple tournaments

def test_tournament_selection_low_is_better():
    """测试 higher_fitness_is_better=False 的情况。"""
    # With low is better, alpha1_best_low (0.1) should be chosen more often.
    # This is hard to assert definitively without many runs or mocking random.sample.
    # We can check if a known "worst" (high fitness) is NOT selected if tournament size is small.

    # Mock random.sample to control tournament contenders
    with patch('random.sample', return_value=[SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER[0], SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER[4]]):
        # Tournament: (alpha1_best_low, 0.1), (alpha5_worst_low, 1.0)
        selected = tournament_selection(SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER, 1, 2, higher_fitness_is_better=False)
        assert len(selected) == 1
        assert selected[0].value == "alpha1_best_low"

    with patch('random.sample', return_value=[SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER[4], SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER[3]]):
        # Tournament: (alpha5_worst_low, 1.0), (alpha4_poor_low, 0.8)
        selected = tournament_selection(SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER, 1, 2, higher_fitness_is_better=False)
        assert len(selected) == 1
        assert selected[0].value == "alpha4_poor_low"


def test_tournament_selection_edge_cases():
    """测试边界情况。"""
    assert tournament_selection([], 2, 2) == [] # 空种群
    assert tournament_selection(SAMPLE_POPULATION_FITNESS, 0, 2) == [] # 选择0个
    assert tournament_selection(SAMPLE_POPULATION_FITNESS, 2, 0) == [] # tournament_size 0
    assert tournament_selection(SAMPLE_POPULATION_FITNESS, 2, 1) is not None # tournament_size 1 (selects self)
    assert len(tournament_selection(SAMPLE_POPULATION_FITNESS, 2, 1)) == 2


# --- roulette_wheel_selection Tests ---
def test_roulette_wheel_selection_basic():
    """测试轮盘赌选择基本功能。"""
    # Fitness: 1.0, 0.8, 0.5, 0.2, 0.1. Total = 2.6
    # Probabilities (approx): 0.38, 0.31, 0.19, 0.08, 0.04
    selected = roulette_wheel_selection(SAMPLE_POPULATION_FITNESS, num_selections=2, higher_fitness_is_better=True)
    assert len(selected) == 2
    for individual in selected:
        assert isinstance(individual, Node)

def test_roulette_wheel_all_equal_fitness():
    """测试所有个体适应度相同时的情况。"""
    pop_equal_fitness = [(Node(f"alpha{i}"), 0.5) for i in range(5)]
    selected = roulette_wheel_selection(pop_equal_fitness, 10, True) # Select 10 times
    assert len(selected) == 10
    # Counts of each alpha should be roughly equal, but hard to assert in one run.

def test_roulette_wheel_low_is_better():
    """测试 higher_fitness_is_better=False 的情况。"""
    # Fitness: 0.1, 0.2, 0.5, 0.8, 1.0. Max=1.0. Shift=1e-9
    # Adjusted (for selection): (1.0-0.1+s), (1.0-0.2+s), ..., (1.0-1.0+s)
    # Approx: 0.9, 0.8, 0.5, 0.2, 0.0 (plus shift)
    # So, alpha1_best_low (original 0.1) should have highest probability.

    # Mock random.uniform to control selection
    # Total adjusted fitness for SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER (higher_fitness_is_better=False)
    # max_fit = 1.0, shift = 1e-9
    # adj_fits = [0.9+s, 0.8+s, 0.5+s, 0.2+s, 0.0+s] => approx sum = 2.4 + 5s
    # If pick is small (e.g., < 0.9), alpha1_best_low should be chosen.
    with patch('random.uniform', return_value=0.1): # Ensure a small pick value
        selected = roulette_wheel_selection(SAMPLE_POPULATION_FITNESS_LOW_IS_BETTER, 1, False)
        assert len(selected) == 1
        assert selected[0].value == "alpha1_best_low"

def test_roulette_wheel_negative_fitness_handling():
    """测试包含负适应度值时的处理。"""
    pop_negative_fitness = [
        (Node("alpha_good"), 0.5),
        (Node("alpha_bad"), -0.5), # Negative
        (Node("alpha_ok"), 0.2)
    ]
    # higher_fitness_is_better=True. min_fit = -0.5. shift = 0.5 + 1e-9
    # adj_fits: (0.5 + shift), (-0.5 + shift), (0.2 + shift)
    # => (1.0+s), (s), (0.7+s) -> all positive.
    selected = roulette_wheel_selection(pop_negative_fitness, 5, True)
    assert len(selected) == 5 # Should still select
    for ind in selected: assert isinstance(ind, Node)

    # higher_fitness_is_better=False. max_fit = 0.5. shift = 1e-9
    # adj_fits: (0.5-0.5+s), (0.5-(-0.5)+s), (0.5-0.2+s)
    # => (s), (1.0+s), (0.3+s) -> all positive. alpha_bad should have highest prob.
    with patch('random.uniform', side_effect=[0.6, 0.7, 0.8, 0.9, 0.95]): # Values targeting the higher cumulative part
        selected_low_better = roulette_wheel_selection(pop_negative_fitness, 5, False)
        assert len(selected_low_better) == 5
        # Check if 'alpha_bad' (which becomes highest adjusted fitness) is selected often
        # This is probabilistic, so direct count assertion is flaky.
        # For a deterministic test, set random.uniform to hit specific segments.

    # Test case where all adjusted fitness values are zero (should fallback to random)
    pop_all_same_negative = [(Node("a"), -1.0), (Node("b"), -1.0)]
    # higher_fitness_is_better=True -> min_fit = -1.0, shift = 1.0+s. adj_fits = [s, s] -> total_adj = 2s
    # higher_fitness_is_better=False -> max_fit = -1.0. adj_fits = [s, s] -> total_adj = 2s
    # This should not result in total_adjusted_fitness <= 0 with the current epsilon logic.
    # Let's test a case where fitness are all zero AFTER adjustment (e.g. if shift was not applied properly)
    with patch('app.core.gp_algo.sum', return_value=0): # Mock sum to be 0
         selected = roulette_wheel_selection(pop_negative_fitness, 2, True)
         assert len(selected) == 2 # Should fallback to random selection


def test_roulette_wheel_edge_cases():
    """测试轮盘赌选择的边界情况。"""
    assert roulette_wheel_selection([], 2, True) == [] # 空种群
    assert roulette_wheel_selection(SAMPLE_POPULATION_FITNESS, 0, True) == [] # 选择0个

    # Single individual population
    single_pop = [(Node("single"), 0.5)]
    selected = roulette_wheel_selection(single_pop, 3, True)
    assert len(selected) == 3
    assert all(ind.value == "single" for ind in selected)

# TODO: Add more tests for selection strategies, especially for roulette wheel with specific
# fitness distributions and mocked random choices to verify probability segments.
# Consider testing elite_selection if it were a standalone function.
# (The conceptual integration shows it as direct sorting, which is simple).
