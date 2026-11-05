package com.capo.ast_extractor.services;

import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.stream.Collectors;

public class AstExtractorEngine {

    private String srcFolderPath;

    public void initSymbolSolver(String srcFolderPath) {
        CombinedTypeSolver typeSolver = new CombinedTypeSolver();
        typeSolver.add(new ReflectionTypeSolver());
        typeSolver.add(new JavaParserTypeSolver(new File(srcFolderPath)));
        JavaSymbolSolver symbolSolver = new JavaSymbolSolver(typeSolver);
        // Records and `instanceof` patterns are the generated project's baseline: parsing at
        // JavaParser's default level rejects the very sources the coder is asked to complete.
        StaticJavaParser.getParserConfiguration()
            .setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE)
            .setSymbolResolver(symbolSolver);
        this.srcFolderPath = srcFolderPath;
    }

    public String extractContext(String targetClass, String targetMethod) throws IOException {
        String simpleName = targetClass.substring(targetClass.lastIndexOf('.') + 1);
        Path file = Paths.get(srcFolderPath, targetClass.replace('.', '/') + ".java");
        CompilationUnit cu = StaticJavaParser.parse(file);

        TypeDeclaration<?> clazz = cu.findFirst(TypeDeclaration.class,
                c -> c.getNameAsString().equals(simpleName))
                .orElseThrow(() -> new IllegalArgumentException("Class not found: " + targetClass));
        MethodDeclaration method = clazz.getMethods().stream()
                .filter(m -> m.getNameAsString().equals(targetMethod))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Method not found: " + targetMethod));

        ObjectMapper mapper = new ObjectMapper();
        ObjectNode root = mapper.createObjectNode();
        root.put("class", targetClass);
        root.put("method", method.getSignature().asString());
        root.put("methodSource", method.toString());
        root.put("fields", clazz.getFields().stream()
                .map(f -> f.toString())
                .collect(Collectors.joining("\n")));
        return mapper.writerWithDefaultPrettyPrinter().writeValueAsString(root);
    }
}