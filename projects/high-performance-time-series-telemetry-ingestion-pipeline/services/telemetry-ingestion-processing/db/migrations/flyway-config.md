# Flyway runner configuration (consumed from src/main/resources/application.yml)

Scripts in this directory are the deployment source. They must be copied
unchanged to `src/main/resources/db/migration/` (packaged on the classpath) by
the config/scaffold unit; the runner then reads them via the Spring namespace:

```yaml
spring:
  r2dbc:
    url: ${TELEMETRY_R2DBC_URL}
  flyway:
    enabled: true
    locations: classpath:db/migration
    url: ${TELEMETRY_JDBC_URL}      # distinct from the R2DBC url
    user: ${TELEMETRY_DB_USER}
    password: ${TELEMETRY_DB_PASSWORD}
```

Test profile document (`---`): `spring.r2dbc.url: r2dbc:h2:mem:///telemetry;NON_KEYWORDS=VALUE`
and `spring.flyway.enabled: false`; slice tests execute the classpath scripts.
No `ddl-auto`, no H2 defaults in the base document.
