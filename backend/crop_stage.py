"""
crop_stage.py - Crop Growth Stage Calculator for THE TARNISHED

This module calculates the crop growth stage based on:
- Crop type (maize, cotton, paddy, chilli)
- Sowing date provided by farmer
- Current date

The crop stage is used as CONTEXT for the advisory engine.
Different diseases affect crops differently at different stages.
"""

from datetime import datetime, date
from typing import Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import re


# ------------------------------------------------------------------
# CROP STAGE DEFINITIONS
# ------------------------------------------------------------------

class CropType(Enum):
    """Supported crop types"""
    MAIZE = "maize"
    COTTON = "cotton"
    PADDY = "paddy"
    CHILLI = "chilli"
    
    @classmethod
    def get_all_crops(cls) -> list:
        """Get list of all supported crop names"""
        return [crop.value for crop in cls]


class GrowthStage(Enum):
    """Standard growth stages for crops"""
    # Generic stages (will be mapped to crop-specific)
    SEEDLING = "seedling"          # 0-20 days
    VEGETATIVE = "vegetative"       # 20-45 days
    REPRODUCTIVE = "reproductive"   # 45-70 days
    MATURITY = "maturity"           # 70-90 days
    HARVEST = "harvest"             # 90+ days
    
    # Maize-specific stages
    MAIZE_GERMINATION = "germination"      # 0-10 days
    MAIZE_SEEDLING = "seedling"            # 10-25 days
    MAIZE_VEGETATIVE = "vegetative"        # 25-50 days
    MAIZE_TASSLING = "tasseling"           # 50-65 days
    MAIZE_SILKING = "silking"              # 65-75 days
    MAIZE_GRAIN_FILL = "grain_fill"        # 75-90 days
    MAIZE_MATURITY = "maturity"            # 90-110 days
    MAIZE_HARVEST = "harvest"              # 110+ days
    
    # Cotton-specific stages
    COTTON_GERMINATION = "germination"     # 0-10 days
    COTTON_SEEDLING = "seedling"           # 10-30 days
    COTTON_SQUARING = "squaring"           # 30-50 days
    COTTON_FLOWERING = "flowering"         # 50-70 days
    COTTON_BOLL_DEVELOPMENT = "boll_development"  # 70-100 days
    COTTON_MATURITY = "maturity"           # 100-120 days
    
    # Paddy-specific stages
    PADDY_NURSERY = "nursery"              # 0-15 days
    PADDY_TRANSPLANTING = "transplanting"  # 15-25 days
    PADDY_TILLERING = "tillering"          # 25-50 days
    PADDY_PANICLE = "panicle_initiation"   # 50-70 days
    PADDY_FLOWERING = "flowering"          # 70-85 days
    PADDY_GRAIN_FILL = "grain_fill"        # 85-100 days
    PADDY_MATURITY = "maturity"            # 100-120 days
    
    # Chilli-specific stages
    CHILLI_GERMINATION = "germination"     # 0-10 days
    CHILLI_SEEDLING = "seedling"           # 10-30 days
    CHILLI_VEGETATIVE = "vegetative"       # 30-50 days
    CHILLI_FLOWERING = "flowering"         # 50-70 days
    CHILLI_FRUIT_SET = "fruit_set"         # 70-90 days
    CHILLI_FRUIT_DEVELOPMENT = "fruit_development"  # 90-110 days
    CHILLI_MATURITY = "maturity"           # 110-130 days


# ------------------------------------------------------------------
# CROP STAGE CONFIGURATION
# ------------------------------------------------------------------

# Each crop has:
# - Total duration (days)
# - Stages with day ranges
# - Stage descriptions
# - Susceptibility to diseases at each stage

CROP_CONFIGS = {
    "maize": {
        "total_days": 110,
        "stages": [
            {"name": "germination", "days": (0, 10), 
             "description": "Seed germination and emergence",
             "susceptibility": "Low - soil-borne diseases possible"},
            {"name": "seedling", "days": (10, 25),
             "description": "Early vegetative growth",
             "susceptibility": "Low - seedling blight risk"},
            {"name": "vegetative", "days": (25, 50),
             "description": "Rapid leaf and stem growth",
             "susceptibility": "Medium - leaf diseases possible"},
            {"name": "tasseling", "days": (50, 65),
             "description": "Tassel emergence (critical period)",
             "susceptibility": "High - rust, blight risk"},
            {"name": "silking", "days": (65, 75),
             "description": "Silk emergence and pollination",
             "susceptibility": "High - ear rot, fungal infections"},
            {"name": "grain_fill", "days": (75, 90),
             "description": "Grain development and filling",
             "susceptibility": "Medium - diseases affect yield"},
            {"name": "maturity", "days": (90, 110),
             "description": "Grain maturation and drying",
             "susceptibility": "Low - lodging risk"},
            {"name": "harvest", "days": (110, 130),
             "description": "Ready for harvest",
             "susceptibility": "Low - post-harvest issues"}
        ]
    },
    "cotton": {
        "total_days": 120,
        "stages": [
            {"name": "germination", "days": (0, 10),
             "description": "Seed germination",
             "susceptibility": "Low - damping off risk"},
            {"name": "seedling", "days": (10, 30),
             "description": "Early growth (4-5 leaves)",
             "susceptibility": "Medium - foliar diseases"},
            {"name": "squaring", "days": (30, 50),
             "description": "Square/bud formation",
             "susceptibility": "High - bollworm, aphids"},
            {"name": "flowering", "days": (50, 70),
             "description": "Flowering stage",
             "susceptibility": "High - pink bollworm, pests"},
            {"name": "boll_development", "days": (70, 100),
             "description": "Boll formation and growth",
             "susceptibility": "Medium - boll rot, pests"},
            {"name": "maturity", "days": (100, 120),
             "description": "Boll opening and maturation",
             "susceptibility": "Low - weather damage"}
        ]
    },
    "paddy": {
        "total_days": 120,
        "stages": [
            {"name": "nursery", "days": (0, 15),
             "description": "Seedling nursery stage",
             "susceptibility": "Medium - blast disease"},
            {"name": "transplanting", "days": (15, 25),
             "description": "Transplanting to field",
             "susceptibility": "High - transplant shock"},
            {"name": "tillering", "days": (25, 50),
             "description": "Tillering stage",
             "susceptibility": "High - stem borer, blast"},
            {"name": "panicle_initiation", "days": (50, 70),
             "description": "Panicle initiation",
             "susceptibility": "High - blast, sheath blight"},
            {"name": "flowering", "days": (70, 85),
             "description": "Flowering stage",
             "susceptibility": "High - false smut"},
            {"name": "grain_fill", "days": (85, 100),
             "description": "Grain filling",
             "susceptibility": "Medium - grain diseases"},
            {"name": "maturity", "days": (100, 120),
             "description": "Grain maturation",
             "susceptibility": "Low - bird damage"}
        ]
    },
    "chilli": {
        "total_days": 130,
        "stages": [
            {"name": "germination", "days": (0, 10),
             "description": "Seed germination",
             "susceptibility": "Low - damping off"},
            {"name": "seedling", "days": (10, 30),
             "description": "Seedling development",
             "susceptibility": "Medium - fungal diseases"},
            {"name": "vegetative", "days": (30, 50),
             "description": "Vegetative growth",
             "susceptibility": "Medium - leaf curl, aphids"},
            {"name": "flowering", "days": (50, 70),
             "description": "Flowering stage",
             "susceptibility": "High - blossom drop"},
            {"name": "fruit_set", "days": (70, 90),
             "description": "Fruit setting",
             "susceptibility": "High - fruit rot, anthracnose"},
            {"name": "fruit_development", "days": (90, 110),
             "description": "Fruit development",
             "susceptibility": "Medium - thrips, mites"},
            {"name": "maturity", "days": (110, 130),
             "description": "Fruit maturation",
             "susceptibility": "Low - post-harvest"}
        ]
    }
}


# ------------------------------------------------------------------
# DATA CLASSES
# ------------------------------------------------------------------

@dataclass
class CropStageInfo:
    """Complete crop stage information"""
    crop: str
    stage_name: str
    stage_description: str
    days_since_sowing: int
    current_date: str
    sowing_date: str
    susceptibility: str
    is_critical: bool
    progress_percentage: float
    days_until_harvest: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON responses"""
        return asdict(self)


# ------------------------------------------------------------------
# CROP STAGE CALCULATOR
# ------------------------------------------------------------------

class CropStageCalculator:
    """Calculate crop growth stage based on sowing date"""
    
    def __init__(self):
        self.today = date.today()
    
    def calculate_stage(
        self, 
        crop: str, 
        sowing_date: str,
        current_date: Optional[str] = None
    ) -> Tuple[Optional[CropStageInfo], Optional[str]]:
        """
        Calculate the current growth stage of a crop.
        
        Args:
            crop: Crop type (maize, cotton, paddy, chilli)
            sowing_date: Date of sowing (YYYY-MM-DD or DD/MM/YYYY)
            current_date: Optional current date (default: today)
            
        Returns:
            Tuple of (CropStageInfo or None, error_message or None)
        """
        # Validate crop
        crop = crop.lower().strip()
        if crop not in CROP_CONFIGS:
            return None, f"Unsupported crop: {crop}. Supported: {', '.join(CROP_CONFIGS.keys())}"
        
        # Parse sowing date
        sowing_dt = self._parse_date(sowing_date)
        if sowing_dt is None:
            return None, f"Invalid sowing date: {sowing_date}. Use YYYY-MM-DD or DD/MM/YYYY"
        
        # Parse current date
        if current_date:
            current_dt = self._parse_date(current_date)
            if current_dt is None:
                return None, f"Invalid current date: {current_date}. Use YYYY-MM-DD or DD/MM/YYYY"
        else:
            current_dt = self.today
        
        # Check if sowing date is in future
        if sowing_dt > current_dt:
            return None, "Sowing date cannot be in the future"
        
        # Calculate days since sowing
        days_since_sowing = (current_dt - sowing_dt).days
        
        # Get crop config
        config = CROP_CONFIGS[crop]
        total_days = config["total_days"]
        
        # Find current stage
        current_stage = None
        for stage in config["stages"]:
            start_day, end_day = stage["days"]
            if start_day <= days_since_sowing <= end_day:
                current_stage = stage
                break
            # If past all stages
            if days_since_sowing > config["stages"][-1]["days"][1]:
                current_stage = config["stages"][-1]
        
        # If before first stage (shouldn't happen with validation)
        if current_stage is None and days_since_sowing < config["stages"][0]["days"][0]:
            current_stage = config["stages"][0]
        
        # If still None, fallback to last stage
        if current_stage is None:
            current_stage = config["stages"][-1]
        
        # Calculate progress
        progress = min(100, (days_since_sowing / total_days) * 100)
        
        # Days until harvest
        days_until_harvest = max(0, total_days - days_since_sowing)
        
        # Determine if critical stage
        is_critical = current_stage["name"] in ["tasseling", "silking", "flowering", "panicle_initiation", "fruit_set"]
        
        # Create info object
        info = CropStageInfo(
            crop=crop,
            stage_name=current_stage["name"],
            stage_description=current_stage["description"],
            days_since_sowing=days_since_sowing,
            current_date=current_dt.strftime("%Y-%m-%d"),
            sowing_date=sowing_dt.strftime("%Y-%m-%d"),
            susceptibility=current_stage["susceptibility"],
            is_critical=is_critical,
            progress_percentage=round(progress, 1),
            days_until_harvest=days_until_harvest
        )
        
        return info, None
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse date from various formats.
        
        Supported formats:
        - YYYY-MM-DD
        - DD/MM/YYYY
        - DD-MM-YYYY
        """
        date_str = date_str.strip()
        
        # Try YYYY-MM-DD
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
        
        # Try DD/MM/YYYY
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            pass
        
        # Try DD-MM-YYYY
        try:
            return datetime.strptime(date_str, "%d-%m-%Y").date()
        except ValueError:
            pass
        
        return None
    
    def get_stage_description(self, crop: str, stage_name: str) -> Optional[str]:
        """Get description of a specific stage"""
        if crop not in CROP_CONFIGS:
            return None
        for stage in CROP_CONFIGS[crop]["stages"]:
            if stage["name"] == stage_name:
                return stage["description"]
        return None
    
    def get_all_stages(self, crop: str) -> Optional[list]:
        """Get all stages for a crop"""
        if crop not in CROP_CONFIGS:
            return None
        return CROP_CONFIGS[crop]["stages"]


# ------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ------------------------------------------------------------------

def get_crop_stage(
    crop: str, 
    sowing_date: str, 
    current_date: Optional[str] = None
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Convenience function to get crop stage info.
    
    Args:
        crop: Crop type (maize, cotton, paddy, chilli)
        sowing_date: Date of sowing
        current_date: Optional current date
        
    Returns:
        Tuple of (dict or None, error_message or None)
    """
    calculator = CropStageCalculator()
    info, error = calculator.calculate_stage(crop, sowing_date, current_date)
    
    if error:
        return None, error
    
    return info.to_dict(), None


def validate_crop(crop: str) -> bool:
    """Check if crop is supported"""
    return crop.lower().strip() in CROP_CONFIGS


def get_supported_crops() -> list:
    """Get list of supported crops"""
    return list(CROP_CONFIGS.keys())


def get_stage_summary(stage_info: CropStageInfo) -> str:
    """Get human-readable summary of crop stage"""
    return (
        f"🌱 {stage_info.crop.title()} at {stage_info.stage_name} stage\n"
        f"   {stage_info.stage_description}\n"
        f"   Days since sowing: {stage_info.days_since_sowing}\n"
        f"   Progress: {stage_info.progress_percentage:.1f}%\n"
        f"   Days to harvest: {stage_info.days_until_harvest}\n"
        f"   Critical stage: {'Yes' if stage_info.is_critical else 'No'}\n"
        f"   Susceptibility: {stage_info.susceptibility}"
    )


# ------------------------------------------------------------------
# TEST CODE
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("🧪 Testing Crop Stage Module...")
    print("-" * 50)
    
    calculator = CropStageCalculator()
    
    # Test with today's date
    test_date = date.today().strftime("%Y-%m-%d")
    
    print(f"\n📅 Today: {test_date}")
    print("\n🌾 Testing maize stages:")
    
    test_scenarios = [
        ("maize", "2026-09-10"),  # 1 day ago (germination)
        ("maize", "2026-08-01"),  # ~39 days ago (vegetative)
        ("maize", "2026-07-01"),  # ~70 days ago (silking)
        ("maize", "2026-05-01"),  # ~131 days ago (harvest)
    ]
    
    for crop, sowing in test_scenarios:
        print(f"\n  Sowing: {sowing}")
        info, error = calculator.calculate_stage(crop, sowing)
        if info:
            print(f"    ✅ Stage: {info.stage_name}")
            print(f"       Days: {info.days_since_sowing}")
            print(f"       Progress: {info.progress_percentage:.1f}%")
            print(f"       Critical: {info.is_critical}")
            print(f"       Description: {info.stage_description}")
        else:
            print(f"    ❌ Error: {error}")
    
    print("\n" + "-" * 50)
    
    print("\n📊 Testing all supported crops:")
    for crop in get_supported_crops():
        print(f"\n  {crop.upper()}:")
        stages = calculator.get_all_stages(crop)
        if stages:
            for stage in stages[:3]:  # Show first 3 stages
                print(f"    - {stage['name']}: {stage['days'][0]}-{stage['days'][1]} days")
            print(f"    ... ({len(stages)-3} more stages)")
    
    print("\n" + "-" * 50)
    print("✅ Crop stage module test complete!")