// system_graph.dsl - Generated from repo analysis
// Version: 1

group api {
  node api "api" // FastAPI
}

group frontend {
  node frontend "frontend" // JavaScript/TypeScript
}

group worker {
  node worker "worker" // RQ
}

group database {
  node database "database" // SQLAlchemy, Alembic
}

group cache {
  node cache "cache" // Redis
}

group external_service {
  node whatsapp_api "whatsapp_api" // WhatsApp Cloud API
  node payment_gateway "payment_gateway" // Stripe
}
