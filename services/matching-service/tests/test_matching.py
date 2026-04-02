import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.matcher import calculate_score, find_best_candidates, CandidateDriver

@pytest.mark.asyncio
async def test_calculate_score():
    # distance=1.0, rating=5.0 -> score = (1.0 * 0.7) + (0.0 * 0.3) = 0.7
    score = await calculate_score(1.0, 5.0)
    assert score == pytest.approx(0.7)
    
    # distance=2.0, rating=4.0 -> score = (2.0 * 0.7) + (1.0 * 0.3) = 1.7
    score = await calculate_score(2.0, 4.0)
    assert score == pytest.approx(1.7)
    
    # distance=0.5, rating=3.0 -> score = (0.5 * 0.7) + (2.0 * 0.3) = 0.35 + 0.6 = 0.95
    score = await calculate_score(0.5, 3.0)
    assert score == pytest.approx(0.95)

@pytest.mark.asyncio
@patch("app.matcher.get_redis")
async def test_find_best_candidates_no_drivers(mock_get_redis):
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis
    mock_redis.georadius.return_value = []
    
    candidates = await find_best_candidates(0.0, 0.0)
    assert candidates == []

@pytest.mark.asyncio
@patch("app.matcher.get_redis")
async def test_find_best_candidates_filtering_and_scoring(mock_get_redis):
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis
    
    # Mock GEORADIUS results: [ (id, dist), ... ]
    mock_redis.georadius.return_value = [
        ("driver-1", 1.0),
        ("driver-2", 2.0),
        ("driver-3", 0.5),
    ]
    
    # Mock status check logic
    async def mock_get(key):
        if "status" in key:
            if "driver-1" in key: return "available"
            if "driver-2" in key: return "busy"  # Should be filtered out
            if "driver-3" in key: return "available"
        if "rating" in key:
            if "driver-1" in key: return "4.5"
            if "driver-3" in key: return "5.0"
        return None

    mock_redis.get.side_effect = mock_get
    
    candidates = await find_best_candidates(0.0, 0.0)
    
    # Expected: driver-3 (dist 0.5, rating 5.0) and driver-1 (dist 1.0, rating 4.5)
    # driver-2 filtered out because busy
    assert len(candidates) == 2
    
    # driver-3 score: (0.5 * 0.7) + (0.0 * 0.3) = 0.35
    # driver-1 score: (1.0 * 0.7) + (0.5 * 0.3) = 0.85
    assert candidates[0].driver_id == "driver-3"
    assert candidates[0].score == pytest.approx(0.35)
    assert candidates[1].driver_id == "driver-1"
    assert candidates[1].score == pytest.approx(0.85)

@pytest.mark.asyncio
@patch("app.matcher.get_redis")
@patch("app.matcher.get_driver_rating_fallback")
async def test_find_best_candidates_rating_fallback(mock_fallback, mock_get_redis):
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis
    
    mock_redis.georadius.return_value = [("driver-4", 1.0)]
    
    # Status is available, but rating is a cache miss
    async def mock_get(key):
        if "status" in key: return "available"
        if "rating" in key: return None # Cache miss
        return None
    
    mock_redis.get.side_effect = mock_get
    mock_fallback.return_value = 4.0
    
    candidates = await find_best_candidates(0.0, 0.0)
    
    assert len(candidates) == 1
    assert candidates[0].driver_id == "driver-4"
    assert candidates[0].rating == 4.0
    mock_fallback.assert_called_once_with("driver-4")
    # Verify it cached the fallback rating
    mock_redis.set.assert_any_call("driver:rating:driver-4", 4.0)
