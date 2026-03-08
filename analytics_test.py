from engine.analytics_engine import AnalyticsEngine


analytics = AnalyticsEngine()

print("\n===== CURIONEST ANALYTICS =====\n")

print("Total Leads:")
print(analytics.total_leads())

print("\nEscalation Distribution:")
print(analytics.escalation_distribution())

print("\nLead Quality Distribution:")
print(analytics.lead_quality_distribution())

print("\nSubject Demand:")
print(analytics.subject_demand())

print("\nChapter Demand:")
print(analytics.chapter_demand())

print("\nEscalation Timeline:")
print(analytics.escalation_timeline())