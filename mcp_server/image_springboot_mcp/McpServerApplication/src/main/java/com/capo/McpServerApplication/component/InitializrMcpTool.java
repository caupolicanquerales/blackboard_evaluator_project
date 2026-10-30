package com.capo.McpServerApplication.component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

@Component
public class InitializrMcpTool {

    private static final Logger log = LoggerFactory.getLogger(InitializrMcpTool.class);
    private static final Pattern SAFE_NAME = Pattern.compile("[A-Za-z0-9_.-]+");
    private static final Pattern SAFE_DEPENDENCIES = Pattern.compile("[A-Za-z0-9_.,-]+");
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss");
    private static final int MAX_LOG_CHARS = 20_000;

    private final WebClient webClient = WebClient.create("https://start.spring.io");
    private final Path projectsDir;
    private final long buildTimeoutMinutes;
    private final String defaultBootVersion;

    public InitializrMcpTool(
            @Value("${mcp.projects.dir:/workspace/projects}") String projectsDir,
            @Value("${mcp.projects.build-timeout-minutes:10}") long buildTimeoutMinutes,
            @Value("${mcp.initializr.default-boot-version:4.1.2}") String defaultBootVersion) {
        this.projectsDir = Path.of(projectsDir).toAbsolutePath().normalize();
        this.buildTimeoutMinutes = buildTimeoutMinutes;
        this.defaultBootVersion = defaultBootVersion;
    }

    @Tool(description = "Generates a Spring Boot Maven project from Spring Initializr, extracts it into the projects folder, "
            + "runs 'mvn clean install -X' inside it and returns the build status, the project path and the end of the build log.")
    public String generateSpringBootProject(
            @ToolParam(description = "Comma-separated Spring Initializr dependency IDs, e.g. web,data-jpa,postgresql") String dependencies,
            @ToolParam(description = "Spring Boot version, e.g. 3.5.6. Optional", required = false) String bootVersion,
            @ToolParam(description = "Maven groupId, e.g. com.example. Optional", required = false) String groupId,
            @ToolParam(description = "Maven artifactId and project folder name (letters, digits, '-', '_', '.'). Optional, default demo", required = false) String artifactId) {

        String group = orDefault(groupId, "com.example");
        String artifact = orDefault(artifactId, "demo");
        String boot = orDefault(bootVersion, defaultBootVersion);
        String deps = dependencies == null ? "" : dependencies.replaceAll("\\s+", "");

        if (!SAFE_NAME.matcher(group).matches() || !SAFE_NAME.matcher(artifact).matches()) {
            return "ERROR: invalid groupId or artifactId";
        }
        if (deps.isEmpty() || !SAFE_DEPENDENCIES.matcher(deps).matches()) {
            return "ERROR: dependencies must be comma-separated Spring Initializr IDs, e.g. web,data-jpa";
        }

        byte[] zip;
        try {
            zip = webClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .path("/starter.zip")
                            .queryParam("type", "maven-project")
                            .queryParam("language", "java")
                            .queryParam("bootVersion", boot)
                            .queryParam("groupId", group)
                            .queryParam("artifactId", artifact)
                            .queryParam("dependencies", deps)
                            .build())
                    .retrieve()
                    .bodyToMono(byte[].class)
                    .block();
        } catch (RuntimeException e) {
            log.error("Spring Initializr request failed", e);
            return "ERROR: could not download project from Spring Initializr: " + e.getMessage();
        }
        if (zip == null || zip.length == 0) {
            return "ERROR: empty response from Spring Initializr";
        }

        try {
            Files.createDirectories(projectsDir);
            String stamp = LocalDateTime.now().format(STAMP);
            Path zipFile = projectsDir.resolve(artifact + "-" + stamp + ".zip");
            Path extractDir = projectsDir.resolve(artifact + "-" + stamp);
            Files.write(zipFile, zip);
            unzip(zipFile, extractDir);

            // starter.zip may have files at the root or inside a top-level folder named after the artifactId
            Path projectDir = Files.exists(extractDir.resolve("pom.xml"))
                    ? extractDir
                    : extractDir.resolve(artifact);
            if (!Files.exists(projectDir.resolve("pom.xml"))) {
                return "ERROR: extracted project has no pom.xml at " + projectDir;
            }

            Path logFile = projectDir.resolve("mvn-build.log");
            Integer exitCode = runMavenBuild(projectDir, logFile);
            return buildReport(exitCode, projectDir, logFile);
        } catch (IOException e) {
            log.error("Project generation failed", e);
            return "ERROR: project generation failed: " + e.getMessage();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return "ERROR: build interrupted";
        }
    }

    private Integer runMavenBuild(Path projectDir, Path logFile) throws IOException, InterruptedException {
        Process process = new ProcessBuilder("mvn", "clean", "install", "-X")
                .directory(projectDir.toFile())
                .redirectErrorStream(true)
                .redirectOutput(logFile.toFile())
                .start();
        if (!process.waitFor(buildTimeoutMinutes, TimeUnit.MINUTES)) {
            process.destroyForcibly();
            return null;
        }
        return process.exitValue();
    }

    private String buildReport(Integer exitCode, Path projectDir, Path logFile) throws IOException {
        String status;
        if (exitCode == null) {
            status = "TIMEOUT (build exceeded " + buildTimeoutMinutes + " minutes and was killed)";
        } else if (exitCode == 0) {
            status = "BUILD SUCCESS";
        } else {
            status = "BUILD FAILURE (exit code " + exitCode + ")";
        }

        String log = Files.readString(logFile, StandardCharsets.UTF_8);
        if (log.length() > MAX_LOG_CHARS) {
            log = "...(truncated)...\n" + log.substring(log.length() - MAX_LOG_CHARS);
        }

        return status + "\n"
                + "Generated project: " + projectDir + "\n"
                + "Full build log: " + logFile + "\n\n"
                + "Last build output:\n" + log;
    }

    private static void unzip(Path zipFile, Path targetDir) throws IOException {
        Files.createDirectories(targetDir);
        Path root = targetDir.toAbsolutePath().normalize();
        try (ZipInputStream zis = new ZipInputStream(Files.newInputStream(zipFile))) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                Path out = root.resolve(entry.getName()).normalize();
                if (!out.startsWith(root)) {
                    throw new IOException("Blocked zip entry outside target folder: " + entry.getName());
                }
                if (entry.isDirectory()) {
                    Files.createDirectories(out);
                } else {
                    Files.createDirectories(out.getParent());
                    Files.copy(zis, out, StandardCopyOption.REPLACE_EXISTING);
                }
                zis.closeEntry();
            }
        }
    }

    private static String orDefault(String value, String fallback) {
        return (value == null || value.isBlank()) ? fallback : value.trim();
    }
}