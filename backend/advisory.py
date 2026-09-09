"""
advisory.py - Agricultural Advisory Engine (MINIMAL TEST VERSION)
"""

from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict


# ------------------------------------------------------------------
# ADVISORY DATA CLASS
# ------------------------------------------------------------------

@dataclass
class Advisory:
    """Complete advisory recommendation"""
    disease: str
    disease_confidence: float
    crop: str
    crop_stage: str
    weather_summary: str
    action: str
    product: str
    dosage: str
    timing: str
    method: str
    safety_precautions: List[str]
    expected_result: str
    weather_risk_level: str
    stage_susceptibility: str
    urgency: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ------------------------------------------------------------------
# DISEASE KNOWLEDGE BASE (Simplified)
# ------------------------------------------------------------------

DISEASE_ADVISORIES = {
    "Common_Rust": {
        "disease_name": "Common Rust",
        "description": "Fungal disease causing reddish-brown pustules on leaves",
        "treatments": [
            {
                "action": "Apply fungicide spray",
                "product": "Propiconazole 25% EC",
                "dosage": "1 ml per liter of water",
                "timing": "At first sign of disease",
                "method": "Spray thoroughly on affected leaves",
                "safety": ["Wear protective clothing", "Wash hands after use"],
                "expected_result": "Controls spread within 5-7 days",
                "stage_specific": {
                    "tasseling": {"urgency": "Immediate", "note": "Critical stage"},
                    "vegetative": {"urgency": "Soon", "note": "Early treatment"}
                }
            }
        ]
    },
    "Gray_Leaf_Spot": {
        "disease_name": "Gray Leaf Spot",
        "description": "Fungal disease causing gray spots on leaves",
        "treatments": [
            {
                "action": "Apply fungicide spray",
                "product": "Azoxystrobin 23% SC",
                "dosage": "1.5 ml per liter of water",
                "timing": "At first symptom",
                "method": "Spray covering both sides of leaves",
                "safety": ["Wear mask and gloves"],
                "expected_result": "Controls infection within 7 days",
                "stage_specific": {
                    "vegetative": {"urgency": "Immediate", "note": "Treat aggressively"}
                }
            }
        ]
    },
    "Healthy": {
        "disease_name": "Healthy Plant",
        "description": "Plant appears healthy",
        "treatments": [
            {
                "action": "Continue good practices",
                "product": "Not applicable",
                "dosage": "Not applicable",
                "timing": "Ongoing",
                "method": "Regular monitoring",
                "safety": ["Follow standard practices"],
                "expected_result": "Maintain healthy crop",
                "stage_specific": {
                    "vegetative": {"urgency": "Plan", "note": "Focus on nutrition"}
                }
            }
        ]
    }
}


# ------------------------------------------------------------------
# ADVISORY ENGINE
# ------------------------------------------------------------------

class AdvisoryEngine:
    def __init__(self):
        self.supported_crops = ["maize"]
        self.disease_kb = DISEASE_ADVISORIES
    
    def generate_advisory(
        self,
        disease: str,
        confidence: float,
        crop: str,
        crop_stage: str,
        weather_risk: Dict,
        stage_info: Dict
    ) -> Tuple[Optional[Advisory], Optional[str]]:
        """Generate a complete advisory recommendation"""
        
        # Validate crop
        crop = crop.lower().strip()
        if crop not in self.supported_crops:
            return None, f"Unsupported crop: {crop}"
        
        # Get disease info
        disease_info = self.disease_kb.get(disease)
        if disease_info is None:
            return None, f"No advisory available for disease: {disease}"
        
        # Get treatment
        stage_name = crop_stage.lower().strip()
        treatment = self._get_treatment_for_stage(disease_info, stage_name)
        
        if treatment is None:
            return None, f"No treatment available for stage: {crop_stage}"
        
        # Build advisory
        advisory = Advisory(
            disease=disease_info["disease_name"],
            disease_confidence=confidence,
            crop=crop,
            crop_stage=crop_stage,
            weather_summary=weather_risk.get("summary", "Weather normal"),
            action=treatment["action"],
            product=treatment["product"],
            dosage=treatment["dosage"],
            timing=treatment["timing"],
            method=treatment["method"],
            safety_precautions=treatment["safety"],
            expected_result=treatment["expected_result"],
            weather_risk_level=weather_risk.get("risk_level", "low"),
            stage_susceptibility=stage_info.get("susceptibility", "Medium"),
            urgency=self._determine_urgency(treatment, stage_name, weather_risk.get("risk_level", "low"))
        )
        
        return advisory, None
    
    def _get_treatment_for_stage(self, disease_info: Dict, stage_name: str) -> Optional[Dict]:
        """Get treatment for specific stage"""
        for treatment in disease_info.get("treatments", []):
            stage_specific = treatment.get("stage_specific", {})
            if stage_name in stage_specific:
                return treatment
        return disease_info["treatments"][0] if disease_info.get("treatments") else None
    
    def _determine_urgency(self, treatment: Dict, stage_name: str, weather_risk: str) -> str:
        """Determine urgency"""
        stage_specific = treatment.get("stage_specific", {})
        if stage_name in stage_specific:
            base = stage_specific[stage_name].get("urgency", "Soon")
            if weather_risk == "high" and base == "Soon":
                return "Immediate"
            return base
        return "Soon"


# ------------------------------------------------------------------
# CONVENIENCE FUNCTIONS
# ------------------------------------------------------------------

def get_advisory(
    disease: str,
    confidence: float,
    crop: str,
    crop_stage: str,
    weather_risk: Dict,
    stage_info: Dict
) -> Tuple[Optional[Dict], Optional[str]]:
    """Convenience function"""
    engine = AdvisoryEngine()
    advisory, error = engine.generate_advisory(
        disease, confidence, crop, crop_stage, weather_risk, stage_info
    )
    if error:
        return None, error
    return advisory.to_dict(), None


# ------------------------------------------------------------------
# TEST CODE - THIS WILL ALWAYS RUN
# ------------------------------------------------------------------

# This prints immediately when you run the file
print("=" * 70)
print("🌾 ADVISORY MODULE LOADED")
print("=" * 70)

# Test 1: Basic sanity check
print("\n✅ Module imported successfully!")
print(f"   Supported diseases: {list(DISEASE_ADVISORIES.keys())}")
print(f"   Supported crops: ['maize']")

# Test 2: Generate a real advisory
print("\n" + "-" * 70)
print("📋 GENERATING ADVISORY FOR Common_Rust")
print("-" * 70)

engine = AdvisoryEngine()

weather_risk = {
    "risk_level": "high",
    "summary": "High humidity and rain expected"
}

stage_info = {
    "susceptibility": "High - critical stage"
}

advisory, error = engine.generate_advisory(
    disease="Common_Rust",
    confidence=0.92,
    crop="maize",
    crop_stage="tasseling",
    weather_risk=weather_risk,
    stage_info=stage_info
)

if advisory:
    print(f"\n✅ ADVISORY GENERATED SUCCESSFULLY!")
    print(f"\n📊 Disease: {advisory.disease}")
    print(f"   Confidence: {advisory.disease_confidence:.2f}")
    print(f"   Crop Stage: {advisory.crop_stage}")
    print(f"   Urgency: {advisory.urgency}")
    print(f"\n📝 Action: {advisory.action}")
    print(f"   Product: {advisory.product}")
    print(f"   Dosage: {advisory.dosage}")
    print(f"   Timing: {advisory.timing}")
    print(f"   Method: {advisory.method}")
    print(f"\n⚠️ Safety Precautions:")
    for safety in advisory.safety_precautions:
        print(f"   • {safety}")
    print(f"\n📈 Expected Result: {advisory.expected_result}")
else:
    print(f"\n❌ Error: {error}")

# Test 3: Gray Leaf Spot
print("\n" + "-" * 70)
print("📋 GENERATING ADVISORY FOR Gray_Leaf_Spot")
print("-" * 70)

weather_risk = {
    "risk_level": "moderate",
    "summary": "Moderate humidity"
}

advisory, error = engine.generate_advisory(
    disease="Gray_Leaf_Spot",
    confidence=0.78,
    crop="maize",
    crop_stage="vegetative",
    weather_risk=weather_risk,
    stage_info={"susceptibility": "Medium"}
)

if advisory:
    print(f"\n✅ ADVISORY GENERATED SUCCESSFULLY!")
    print(f"\n📊 Disease: {advisory.disease}")
    print(f"   Confidence: {advisory.disease_confidence:.2f}")
    print(f"   Crop Stage: {advisory.crop_stage}")
    print(f"   Urgency: {advisory.urgency}")
    print(f"\n📝 Action: {advisory.action}")
    print(f"   Product: {advisory.product}")
    print(f"   Dosage: {advisory.dosage}")
    print(f"   Timing: {advisory.timing}")
else:
    print(f"\n❌ Error: {error}")

# Test 4: Healthy
print("\n" + "-" * 70)
print("📋 GENERATING ADVISORY FOR Healthy")
print("-" * 70)

weather_risk = {
    "risk_level": "low",
    "summary": "Normal weather"
}

advisory, error = engine.generate_advisory(
    disease="Healthy",
    confidence=0.95,
    crop="maize",
    crop_stage="vegetative",
    weather_risk=weather_risk,
    stage_info={"susceptibility": "Low"}
)

if advisory:
    print(f"\n✅ ADVISORY GENERATED SUCCESSFULLY!")
    print(f"\n📊 Disease: {advisory.disease}")
    print(f"   Confidence: {advisory.disease_confidence:.2f}")
    print(f"   Crop Stage: {advisory.crop_stage}")
    print(f"   Urgency: {advisory.urgency}")
    print(f"\n📝 Action: {advisory.action}")
    print(f"   Product: {advisory.product}")
    print(f"   Method: {advisory.method}")
else:
    print(f"\n❌ Error: {error}")

print("\n" + "=" * 70)
print("✅ ADVISORY MODULE TEST COMPLETE!")
print("=" * 70)