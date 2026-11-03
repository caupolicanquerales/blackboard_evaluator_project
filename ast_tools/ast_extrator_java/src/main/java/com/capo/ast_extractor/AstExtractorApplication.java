package com.capo.ast_extractor;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;
import java.util.concurrent.Callable;
import com.capo.ast_extractor.services.AstExtractorEngine;

@SpringBootApplication
@Command(name = "ast-extractor", mixinStandardHelpOptions = true, version = "1.0",
         description = "Extracts lightweight AST context for LLM agents.")
public class AstExtractorApplication implements Callable<Integer> {

	@Option(names = {"-s", "--src-dir"}, required = true, description = "Path to project src/main/java")
    private String srcDir;

    @Option(names = {"-t", "--target-class"}, required = true, description = "Fully qualified target class name")
    private String targetClass;

    @Option(names = {"-m", "--target-method"}, required = true, description = "Target method name to implement")
    private String targetMethod;

    @Override
    public Integer call() throws Exception {
        AstExtractorEngine engine = new AstExtractorEngine();
        engine.initSymbolSolver(srcDir);
        String jsonContext = engine.extractContext(targetClass, targetMethod);
        System.out.println(jsonContext);
        return 0;
    }

	public static void main(String[] args) {
		int exitCode = new CommandLine(new AstExtractorApplication()).execute(args);
        System.exit(exitCode);
	}

}
