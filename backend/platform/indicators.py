"""Causal indicator library. No fitted transforms or future observations."""
import numpy as np
import pandas as pd
import hashlib
import os
import tempfile
from pathlib import Path

PERIODS = (7, 14, 21, 50)

def cached_indicators(df, cache_dir=None):
    if cache_dir is None:
        return indicator_frame(df)
    # Cache contains causal numeric columns only; no trained transforms/labels.
    digest = hashlib.sha256(Path(__file__).read_bytes())
    digest.update(pd.util.hash_pandas_object(df[['open','high','low','close']], index=True).values.tobytes())
    digest.update(pd.__version__.encode())
    folder = Path(cache_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (digest.hexdigest()+'.npz')
    names = indicator_names()
    if path.exists():
        try:
            with np.load(path, allow_pickle=False) as data:
                values = data['values']
                if values.shape == (len(df),len(names)):
                    return pd.DataFrame(values,index=df.index,columns=names)
        except (OSError,ValueError,KeyError):
            pass
    frame = indicator_frame(df)[names]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder,suffix='.npz',delete=False) as handle:
            temporary = handle.name
            np.savez_compressed(handle,values=frame.to_numpy())
        os.replace(temporary,path)
    finally:
        if temporary and os.path.exists(temporary): os.unlink(temporary)
    return frame

def indicator_names():
    return [f"{kind}_{period}" for period in PERIODS for kind in ("rsi", "ema", "atr", "bb_position")]

def indicator_frame(df):
    close = df.close
    delta = close.diff()
    true_range = pd.concat([df.high-df.low, (df.high-close.shift()).abs(), (df.low-close.shift()).abs()], axis=1).max(axis=1)
    result = pd.DataFrame(index=df.index)
    for period in PERIODS:
        gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        result[f"rsi_{period}"] = (100*gain/(gain+loss)).where(gain+loss != 0, 50)
        result[f"ema_{period}"] = close/close.ewm(span=period, adjust=False, min_periods=period).mean()-1
        result[f"atr_{period}"] = true_range.ewm(alpha=1/period, adjust=False, min_periods=period).mean()/close
        mean, std = close.rolling(period).mean(), close.rolling(period).std()
        result[f"bb_position_{period}"] = ((close-mean)/(4*std)+.5).where(std != 0, .5)
    return result.replace([np.inf, -np.inf], np.nan)

def rule_masks(frame, rules):
    masks = []
    for side in (rules.long, rules.short):
        mask = pd.Series(True, index=frame.index)
        for rule in side:
            if rule.feature not in frame:
                raise ValueError(f"Kural indikatörü bulunamadı: {rule.feature}")
            x = frame[rule.feature]
            if rule.operator == "gt": condition = x > rule.value
            elif rule.operator == "lt": condition = x < rule.value
            elif rule.operator == "cross_above": condition = (x > rule.value) & (x.shift() <= rule.value)
            else: condition = (x < rule.value) & (x.shift() >= rule.value)
            mask &= condition.fillna(False)
        masks.append(mask.to_numpy())
    return masks

def apply_rules(prediction, masks):
    long, short = masks
    return np.where(((prediction > 0) & long) | ((prediction < 0) & short), prediction, 0.0)
