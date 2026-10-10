"""Interface translations. Missing keys fall back to English. Have native speakers review before release."""
LANGS = {"en": "English", "hi": "हिन्दी"}

T = {
"en": {
 "title": "Healthcare Intelligence",
 "caption": "Evidence-first search over 10,000 facility listings. It shows what the records say, the exact quote behind it, and what it cannot verify.",
 "emergency": "**In an emergency call 112 (or your local ambulance) first.** This is a decision-support prototype built on scraped listing data. It is not a clinical authority and does not show live beds or doctors. Always phone the facility before travelling.",
 "q_label": "What do you need, and where?", "search": "Search", "examples": "Try an example", "lang": "Language",
 "s1": "1. What we understood", "s2": "2. Best-supported matches", "s3": "3. Why not these?", "s4": "4. What we could not verify",
 "verified": "Verified", "partial": "Partially verified", "unverified": "Unverified",
 "status": "Status", "distance": "Distance", "trust": "Trust", "unver_exp": "Unverified options",
 "no_results": "No facility in this area has enough evidence for everything you asked. That is a data gap, not proof that care is unavailable. See the unverified list below, and call ahead.",
 "add_pin": "Add a PIN code or city to the search to see distance.", "source": "Source: dataset row"},
"hi": {
 "title": "स्वास्थ्य सूचना खोज",
 "caption": "10,000 सुविधा सूचियों में प्रमाण-आधारित खोज। यह दिखाती है कि रिकॉर्ड क्या कहते हैं, उसके पीछे का सटीक उद्धरण, और क्या सत्यापित नहीं हो सका।",
 "emergency": "**आपात स्थिति में पहले 112 पर कॉल करें।** यह केवल निर्णय-सहायता प्रोटोटाइप है, जो सूचीबद्ध डेटा पर बना है। यह चिकित्सा प्राधिकरण नहीं है और लाइव बेड या डॉक्टर नहीं दिखाता। जाने से पहले सुविधा को फ़ोन ज़रूर करें।",
 "q_label": "आपको क्या चाहिए, और कहाँ?", "search": "खोजें", "examples": "उदाहरण आज़माएँ", "lang": "भाषा",
 "s1": "1. हमने क्या समझा", "s2": "2. सबसे अच्छे प्रमाण वाले परिणाम", "s3": "3. ये क्यों नहीं?", "s4": "4. हम क्या सत्यापित नहीं कर सके",
 "verified": "सत्यापित", "partial": "आंशिक रूप से सत्यापित", "unverified": "असत्यापित",
 "status": "स्थिति", "distance": "दूरी", "trust": "भरोसा", "unver_exp": "असत्यापित विकल्प",
 "no_results": "इस क्षेत्र में किसी सुविधा के पास आपकी हर माँग के लिए पर्याप्त प्रमाण नहीं है। यह डेटा की कमी है, देखभाल न होने का प्रमाण नहीं। नीचे असत्यापित सूची देखें और पहले फ़ोन करें।",
 "add_pin": "दूरी देखने के लिए खोज में पिन कोड या शहर जोड़ें।", "source": "स्रोत: डेटासेट पंक्ति"},
}

def t(key, lang="en"):
    return T.get(lang, {}).get(key) or T["en"].get(key, key)