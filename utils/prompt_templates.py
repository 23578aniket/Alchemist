# utils/prompt_templates.py
# This module centralizes all LLM prompt templates.
# Using f-strings for easy variable injection.

# --- Data Ingestion & Parsing Prompts ---
NICHE_SCHEMA_PROMPT_SOLAR_PUMP_RAJA = """
Extract comprehensive information about small-scale solar pump systems, specifically relevant for farmers in Rajasthan.
Focus on:
- **Solar pump model name/number:** (e.g., "SolarTech SP-100", "Kirloskar KSP-5")
- **Manufacturer:** (e.g., "SunPower India", "Shakti Pumps")
- **Common error codes and their meaning:** (e.g., "E01: Low Voltage", "F03: Motor Overload")
- **Detailed troubleshooting steps for specific errors:** (e.g., "For E01: 1. Check panel connections. 2. Clean solar panels. 3. Inspect wiring for damage.")
- **Regular maintenance schedule/tasks:** (e.g., "Daily visual inspection", "Monthly panel cleaning", "Quarterly water level check")
- **Required tools/parts for maintenance/repair:** (e.g., "Multimeter", "Wrench set", "Spare fuse", "Cleaning brush")
- **Typical costs for parts (mention INR if possible):** (e.g., "Fuse: ₹50", "Motor Bearing: ₹500")
- **Safety precautions:** (e.g., "Always turn off power before maintenance", "Wear insulated gloves")
- **Best practices for efficiency:** (e.g., "Orient panels correctly", "Keep panels clean", "Ensure proper water flow")
- **Government subsidies or schemes related to solar pumps in Rajasthan:** (mention scheme name, eligibility criteria, application process, required documents, official portal links if available).

Return the extracted data as a single JSON object. If a specific field is not found in the text, omit that field from the JSON.
Example JSON structure:
{{
  "pump_model": "SolarTech SP-100",
  "manufacturer": "SunPower India",
  "error_codes": [
    {{"code": "E01", "description": "Low Voltage", "troubleshooting_steps": ["Check panel connections", "Clean panels thoroughly"]}},
    {{"code": "F03", "description": "Motor Overload", "troubleshooting_steps": ["Check pump for blockages", "Verify motor current"]}}
  ],
  "maintenance_schedule": ["Daily visual inspection of panels", "Monthly cleaning of solar panels", "Quarterly check of wiring and connections"],
  "required_tools_parts": ["Multimeter", "Adjustable wrench", "Soft brush for cleaning"],
  "typical_costs": {{"fuse_inr": 50, "motor_bearing_inr": 500}},
  "safety_precautions": ["Turn off power before any work", "Avoid touching wet components"],
  "efficiency_tips": ["Ensure panels face south", "Clean panels regularly"],
  "gov_schemes": [
    {{"name": "PM KUSUM Yojana", "eligibility": "Small and marginal farmers in Rajasthan", "application_process": "Apply online via Raj Kisan Saathi portal", "documents_required": ["Aadhaar Card", "Land Records", "Bank Passbook"]}}
  ]
}}
"""

# --- Content Generation Prompts ---

ARTICLE_GENERATION_PROMPT_HI = """
आप राजस्थान के किसानों के लिए कृषि प्रौद्योगिकी के विशेषज्ञ तकनीकी लेखक हैं।
आपका कार्य निम्नलिखित संरचित डेटा के बारे आधार पर सौर पंप प्रणालियों के लिए एक व्यापक, अत्यधिक व्यावहारिक और आसानी से समझ में आने वाली मार्गदर्शिका हिंदी में तैयार करना है:
---
डेटा: {structured_data_json}
---
मुख्य शब्द (हिंदी): {seo_keywords_hindi}

**निर्देश:**
1.  **शीर्षक:** एक आकर्षक और कीवर्ड-समृद्ध शीर्षक हिंदी में बनाएं।
2.  **परिचय:** विषय का संक्षिप्त परिचय दें, किसानों के लिए इसके महत्व पर जोर दें।
3.  **मुख्य खंड:** `structured_data_json` के आधार पर अलग-अलग खंड बनाएं।
    * समस्या निवारण के लिए, स्पष्ट, क्रमांकित चरण प्रदान करें।
    * रखरखाव के लिए, अनुसूची और कार्यों का विवरण दें।
    * सरकारी योजनाओं के लिए, पात्रता और आवेदन प्रक्रिया को सरलता से समझाएं।
4.  **व्यावहारिक सलाह:** इसमें व्यावहारिक सुझाव और "क्या करें" मार्गदर्शन शामिल करें।
5.  **भाषा और टोन:** स्पष्ट, सरल हिंदी का प्रयोग करें। अत्यधिक तकनीकी शब्दजाल से बचें। सहायक और उत्साहवर्धक बनें।
6.  **फॉर्मेटिंग:** पठनीयता के लिए H1, H2 टैग, बोल्डिंग, बुलेट पॉइंट और क्रमांकित सूचियों का उपयोग करें।
7.  **न्यूनतम लंबाई:** कम से कम {min_length} शब्दों का लक्ष्य रखें।
8.  **एआई अस्वीकरण:** लेख के अंत में, स्पष्ट रूप से दिखाई देने वाला निम्नलिखित अस्वीकरण शामिल करें: "{ai_disclaimer_text}"।

आपका उत्पन्न किया गया लेख:
"""

ARTICLE_GENERATION_PROMPT_EN = """
You are an expert technical writer specializing in agricultural technology for farmers in Rajasthan.
Your task is to create a comprehensive, highly practical, and easy-to-understand guide in English about the following structured data:
---
Data: {structured_data_json}
---
Target Keywords (English): {seo_keywords_english}

**Instructions:**
1.  **Title:** Create a compelling and keyword-rich title in English.
2.  **Introduction:** Briefly introduce the topic, emphasizing its importance for farmers.
3.  **Main Sections:** Based on the `structured_data_json`, create distinct sections.
    * For troubleshooting, provide clear, numbered steps.
    * For maintenance, detail the schedule and actions.
    * For government schemes, explain eligibility and application process simply.
4.  **Practical Advice:** Include actionable tips and "what to do" guidance.
5.  **Language & Tone:** Use clear, simple English. Avoid overly technical jargon. Be helpful and encouraging.
6.  **Formatting:** Use H1, H2 tags, bolding, bullet points, and numbered lists for readability.
7.  **Minimum Length:** Aim for at least {min_length} words.
8.  **AI Disclaimer:** Include the following at the very end of the article, clearly visible: "{ai_disclaimer_text}".

Your generated article:
"""

IMAGE_PROMPT_GENERATION_PROMPT = """
From the following article content, identify 3-5 key concepts or topics that would benefit from illustrative images or diagrams.
For each concept, provide a concise (10-15 word) image generation prompt suitable for a text-to-image model.
The prompts should be specific and describe the visual.
Return as a JSON list of objects, each with a "concept" and "prompt" key.

Example:
[
  {{"concept": "Solar Panel Cleaning", "prompt": "A farmer cleaning solar panels with a soft brush under a bright sun in a rural Indian field."}},
  {{"concept": "Pump Troubleshooting", "prompt": "A close-up of a solar pump control panel displaying an error code with a farmer looking concerned."}}
]

Article content: {article_text}
"""

VIDEO_SCRIPT_SUMMARY_PROMPT = """
Summarize the key information from the following article into a concise, engaging video script (max {max_duration_seconds} seconds) suitable for farmers in Rajasthan.
The script should be in {language_name} and include clear, simple sentences suitable for narration.
Break the script into short, logical segments.

Article: {article_text}
"""

# --- SEO Prompts ---
SEO_OPTIMIZATION_PROMPT = """
Given the following article content and its primary topic '{article_title}',
suggest an optimized meta title (max 60 chars), meta description (max 160 chars),
and identify 3-5 relevant internal linking opportunities (i.e., keywords/phrases within the article
that could link to another relevant article within the '{niche_topic}' domain).
For internal links, suggest the 'keyword' and a 'target_topic' that it would link to.
Return as JSON:
{{
  "meta_title": "...",
  "meta_description": "...",
  "internal_links": [
    {{"keyword": "...", "target_topic": "..."}},
    ...
  ]
}}

Article content: {article_text}
"""

# --- Monetization Prompts ---
AFFILIATE_LINK_OPPORTUNITY_PROMPT = """
Identify opportunities within the following article to naturally integrate Amazon India affiliate links for products related to small-scale solar pump systems (e.g., solar panels, small pumps, batteries, wiring, tools, maintenance kits).
For each opportunity, suggest a relevant product type and the exact keyword phrase in {language_name} from the article text to link.
Prioritize keywords that clearly indicate a product or tool.
Return as JSON:
{{
  "affiliate_links": [
    {{"keyword": "...", "product_type": "...", "amazon_search_term": "..."}},
    ...
  ]
}}

Article content: {article_text}
"""

# --- Performance Analysis Prompts ---
PERFORMANCE_ANALYSIS_PROMPT = """
Analyze the following content performance data.
Identify clear trends (e.g., high-performing topics, low-performing platforms, content types with low revenue).
Suggest specific, actionable directives for content generation (e.g., "Generate more articles on X topic"),
SEO (e.g., "Prioritize Y keywords"), and distribution (e.g., "Publish more on Z platform").
Consider the costs associated with LLM calls and content generation to ensure profitability.
Prioritize directives that maximize revenue and traffic efficiency.

Data: {performance_data_json}

Return directives as a JSON list, e.g.:
{{
    "directives": [
        {{"agent": "content_generation", "action": "generate_more", "topic_focus": "solar_panel_cleaning", "quantity": 5, "language": "hi"}},
        {{"agent": "seo_distribution", "action": "re_optimize_meta", "content_ids": [123, 456], "focus": "conversion"}},
        {{"agent": "monetization_feedback", "action": "adjust_ad_density", "pages_type": "high_traffic"}}
    ]
}}
"""
