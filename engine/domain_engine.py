class DomainEngine:

    def __init__(self):

        self.domains = {
            "education": {
                "fields": ["subject", "chapter"]
            },
            "saas": {
                "fields": ["product", "feature"]
            },
            "consulting": {
                "fields": ["service", "topic"]
            }
        }

    def resolve_domain(self, data):

        domain = data.get("domain", "education")

        if domain not in self.domains:
            domain = "education"

        return domain

    def build_context(self, domain, data):

        if domain == "education":
            return {
                "subject": data.get("subject"),
                "chapter": data.get("chapter")
            }

        if domain == "saas":
            return {
                "product": data.get("product"),
                "feature": data.get("feature")
            }

        if domain == "consulting":
            return {
                "service": data.get("service"),
                "topic": data.get("topic")
            }

        return {}