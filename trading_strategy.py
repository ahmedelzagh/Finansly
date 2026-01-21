"""
Real-world trading strategy indicators for buy/sell signals
Uses Moving Averages, RSI, and Support/Resistance levels
"""
from typing import List, Optional, Tuple


def calculate_sma(prices: List[float], period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average (SMA)
    
    Args:
        prices: List of prices (most recent last)
        period: Number of periods for SMA
        
    Returns:
        SMA value or None if not enough data
    """
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """
    Calculate Exponential Moving Average (EMA)
    Gives more weight to recent prices
    
    Args:
        prices: List of prices (most recent last)
        period: Number of periods for EMA
        
    Returns:
        EMA value or None if not enough data
    """
    if len(prices) < period:
        return None
    
    # Start with SMA
    ema = calculate_sma(prices[:period], period)
    multiplier = 2 / (period + 1)
    
    # Calculate EMA for remaining prices
    for price in prices[period:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    
    return ema


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Relative Strength Index (RSI)
    RSI < 30 = Oversold (potential buy)
    RSI > 70 = Overbought (potential sell)
    
    Args:
        prices: List of prices (most recent last)
        period: RSI period (default 14)
        
    Returns:
        RSI value (0-100) or None if not enough data
    """
    if len(prices) < period + 1:
        return None
    
    # Calculate price changes
    gains = []
    losses = []
    max_abs_change = 0.0
    
    for i in range(len(prices) - period, len(prices)):
        if i == 0:
            continue
        change = prices[i] - prices[i - 1]
        max_abs_change = max(max_abs_change, abs(change))
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return None
    
    # Calculate average gain and loss
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    # If price barely moved at all, treat as neutral (RSI ~ 50)
    last_price = prices[-1]
    if last_price != 0:
        # Relative max move below 0.05% of price → essentially flat
        if (max_abs_change / abs(last_price)) < 0.0005:
            return 50.0
    
    if avg_loss == 0:
        return 100  # All gains, no losses (strong up-move)
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)


def find_support_resistance(prices: List[float], lookback: int = 20) -> Tuple[Optional[float], Optional[float]]:
    """
    Find support (low) and resistance (high) levels
    
    Args:
        prices: List of prices (most recent last)
        lookback: Number of periods to look back
        
    Returns:
        Tuple of (support_level, resistance_level)
    """
    if len(prices) < lookback:
        return (None, None)
    
    recent_prices = prices[-lookback:]
    support = min(recent_prices)
    resistance = max(recent_prices)
    
    return (support, resistance)


def analyze_trend(prices: List[float], short_period: int = 10, long_period: int = 30) -> Optional[str]:
    """
    Analyze price trend using moving averages
    
    Args:
        prices: List of prices (most recent last)
        short_period: Short-term MA period
        long_period: Long-term MA period
        
    Returns:
        "bullish", "bearish", or None
    """
    short_ma = calculate_sma(prices, short_period)
    long_ma = calculate_sma(prices, long_period)
    
    if short_ma is None or long_ma is None:
        return None
    
    if short_ma > long_ma:
        return "bullish"
    elif short_ma < long_ma:
        return "bearish"
    return None


def get_trading_signal(
    prices: List[float],
    current_price: float,
    min_history: int = 30
) -> Tuple[Optional[str], dict]:
    """
    Generate buy/sell signal using multiple indicators
    
    Strategy:
    - Moving Average Crossover (SMA 10 vs SMA 30)
    - RSI (oversold/overbought)
    - Support/Resistance levels
    - Requires multiple confirmations for reliability
    
    Args:
        prices: Historical prices (most recent last)
        current_price: Current price
        min_history: Minimum history required for analysis
        
    Returns:
        Tuple of (signal: "BUY"/"SELL"/None, analysis_dict)
    """
    if len(prices) < min_history:
        return (None, {"reason": "Insufficient price history", "required": min_history, "available": len(prices)})
    
    analysis = {
        "current_price": current_price,
        "indicators": {}
    }
    
    # Calculate indicators
    sma_10 = calculate_sma(prices, 10)
    sma_30 = calculate_sma(prices, 30)
    rsi = calculate_rsi(prices, 14)
    support, resistance = find_support_resistance(prices, 20)
    trend = analyze_trend(prices, 10, 30)
    
    analysis["indicators"] = {
        "sma_10": sma_10,
        "sma_30": sma_30,
        "rsi": rsi,
        "support": support,
        "resistance": resistance,
        "trend": trend
    }
    
    # Count confirmations
    buy_signals = 0
    sell_signals = 0
    reasons = []
    
    # Signal 1: Moving Average Crossover
    if sma_10 and sma_30:
        if sma_10 > sma_30:
            buy_signals += 1
            reasons.append("MA: Short-term above long-term (bullish)")
        elif sma_10 < sma_30:
            sell_signals += 1
            reasons.append("MA: Short-term below long-term (bearish)")
    
    # Signal 2: RSI
    if rsi is not None:
        if rsi < 30:
            buy_signals += 2  # Strong buy signal (oversold)
            reasons.append(f"RSI: Oversold ({rsi:.1f})")
        elif rsi > 70:
            sell_signals += 2  # Strong sell signal (overbought)
            reasons.append(f"RSI: Overbought ({rsi:.1f})")
        elif rsi < 40:
            buy_signals += 1  # Weak buy signal
            reasons.append(f"RSI: Approaching oversold ({rsi:.1f})")
        elif rsi > 60:
            sell_signals += 1  # Weak sell signal
            reasons.append(f"RSI: Approaching overbought ({rsi:.1f})")
    
    # Signal 3: Support/Resistance
    if support and resistance:
        price_range = resistance - support
        if price_range > 0:
            price_position = (current_price - support) / price_range
            
            if price_position < 0.2:  # Near support (20% from bottom)
                buy_signals += 1
                reasons.append(f"Price near support level ({support:.2f})")
            elif price_position > 0.8:  # Near resistance (80% from bottom)
                sell_signals += 1
                reasons.append(f"Price near resistance level ({resistance:.2f})")
    
    # Signal 4: Trend analysis
    if trend == "bullish":
        buy_signals += 1
        reasons.append("Trend: Bullish")
    elif trend == "bearish":
        sell_signals += 1
        reasons.append("Trend: Bearish")
    
    # Require at least 2 confirmations for a signal
    MIN_CONFIRMATIONS = 2
    
    analysis["buy_signals"] = buy_signals
    analysis["sell_signals"] = sell_signals
    analysis["reasons"] = reasons
    
    if buy_signals >= MIN_CONFIRMATIONS:
        return ("BUY", analysis)
    elif sell_signals >= MIN_CONFIRMATIONS:
        return ("SELL", analysis)
    
    return (None, analysis)
