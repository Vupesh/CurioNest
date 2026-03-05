from engine.analytics_engine import AnalyticsEngine


def run_analytics():

    analytics = AnalyticsEngine()

    print("\n===== CurioNest Analytics Report =====\n")

    print("1. Total Leads")
    print("----------------")
    print(analytics.get_total_leads())

    print("\n2. Escalation Signals")
    print("----------------")
    signals = analytics.get_escalation_summary()
    for row in signals:
        print(row)

    print("\n3. Teacher Demand Heatmap")
    print("----------------")
    demand = analytics.get_teacher_demand()
    for row in demand:
        print(row)

    print("\n4. Lead Funnel Distribution")
    print("----------------")
    funnel = analytics.get_lead_distribution()
    for row in funnel:
        print(row)

    print("\n5. Escalation Timeline")
    print("----------------")
    trend = analytics.get_escalation_trend()
    for row in trend:
        print(row)

    print("\n6. Engagement Metrics")
    print("----------------")
    print(analytics.get_engagement_metrics())


if __name__ == "__main__":
    run_analytics()
    