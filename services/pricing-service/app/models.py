"""Pricing service models."""

from sqlalchemy import Column, Integer, String, Float, DateTime
from shared.database import Base

# No SQL models for pricing for now — everything is Redis-based surge.
