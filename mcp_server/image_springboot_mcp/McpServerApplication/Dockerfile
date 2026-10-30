# ==========================================
# STAGE 1: Build Java Jar with Maven
# ==========================================
FROM maven:3.9.6-eclipse-temurin-21-alpine AS builder
WORKDIR /app

# Cache dependencies
COPY pom.xml .
RUN mvn dependency:go-offline

# Package executable JAR
COPY src ./src
RUN mvn clean package -DskipTests

# ==========================================
# STAGE 2: Minimal Production Runtime
# ==========================================
# Runtime needs Maven and a JDK because the server runs "mvn clean install -X" on generated projects
FROM maven:3.9.6-eclipse-temurin-21-alpine
WORKDIR /app

COPY --from=builder /app/target/*.jar app.jar

ENV MCP_PROJECTS_DIR=/workspace/projects
VOLUME /workspace
EXPOSE 8900

ENTRYPOINT ["java", "-jar", "app.jar"]