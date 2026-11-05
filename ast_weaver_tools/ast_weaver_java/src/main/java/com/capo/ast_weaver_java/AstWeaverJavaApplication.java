package com.capo.ast_weaver_java;

import com.capo.ast_weaver_java.records.CoderChangesPayload;
import com.capo.ast_weaver_java.services.JavaASTWeaver;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Objects;
import java.util.Optional;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.ExitCodeGenerator;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class AstWeaverJavaApplication implements CommandLineRunner, ExitCodeGenerator {

    private static final String USAGE =
        "Usage: java -jar code-weaver.jar --root <project_root> --changes-json <payload_path>";

    private final ObjectMapper mapper;

    private int exitCode;

    public AstWeaverJavaApplication(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    @Bean
    static ObjectMapper coderChangesObjectMapper() {
        return new ObjectMapper();
    }

    public static void main(String[] args) {
        System.exit(SpringApplication.exit(SpringApplication.run(AstWeaverJavaApplication.class, args)));
    }

    @Override
    public void run(String... args) {
        try {
            weaveFrom(args);
            exitCode = 0;
        } catch (Exception ex) {
            System.err.println("ERROR: " + ex.getMessage());
            exitCode = 1;
        }
    }

    @Override
    public int getExitCode() {
        return exitCode;
    }

    private void weaveFrom(String... args) throws Exception {
        CliOptions options = parseOptions(args)
            .orElseThrow(() -> new IllegalArgumentException(USAGE));
        CoderChangesPayload payload = mapper.readValue(options.changesJson().toFile(), CoderChangesPayload.class);
        Path targetPath = resolveWithinRoot(options.root(), payload.targetFile());
        JavaASTWeaver.weave(targetPath, payload);
        System.out.println("Successfully spliced AST body into: " + targetPath);
    }

    private static Optional<CliOptions> parseOptions(String... args) {
        Path root = null;
        Path changesJson = null;
        for (int i = 0; i < args.length; i++) {
            if ("--root".equals(args[i]) && i + 1 < args.length) {
                root = Path.of(args[++i]).toAbsolutePath().normalize();
            } else if ("--changes-json".equals(args[i]) && i + 1 < args.length) {
                changesJson = Path.of(args[++i]).toAbsolutePath().normalize();
            }
        }
        if (root == null || changesJson == null) {
            return Optional.empty();
        }
        if (!Files.isRegularFile(changesJson)) {
            throw new IllegalArgumentException("Changes JSON payload not found at " + changesJson);
        }
        return Optional.of(new CliOptions(root, changesJson));
    }

    private static Path resolveWithinRoot(Path root, String targetFile) {
        Path targetPath = root.resolve(targetFile).normalize();
        if (!targetPath.startsWith(root)) {
            throw new IllegalArgumentException("targetFile escapes project root: " + targetFile);
        }
        return targetPath;
    }

    private record CliOptions(Path root, Path changesJson) {

        CliOptions {
            Objects.requireNonNull(root, "root is required");
            Objects.requireNonNull(changesJson, "changesJson is required");
        }
    }
}
