package com.capo.ast_weaver_java.records;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Objects;

@JsonIgnoreProperties(ignoreUnknown = true)
public record CoderChangesPayload(
    String id,
    String project,
    String targetFile,
    String export,
    String method,
    String language,
    String framework,
    String signature,
    String returns,
    String kind,
    List<String> members,
    List<String> imports,
    String body,
    List<String> missing,
    List<String> annotations,
    List<String> methodAnnotations,
    boolean executed,
    @JsonProperty("extends") String extendsType,
    @JsonProperty("implements") List<String> implementsTypes
) {

    public CoderChangesPayload {
        Objects.requireNonNull(targetFile, "targetFile is required");
        Objects.requireNonNull(export, "export is required");
        Objects.requireNonNull(method, "method is required");
        Objects.requireNonNull(body, "body is required");
        imports = imports == null ? List.of() : List.copyOf(imports);
        missing = missing == null ? List.of() : List.copyOf(missing);
        members = members == null ? List.of() : List.copyOf(members);
        annotations = annotations == null ? List.of() : List.copyOf(annotations);
        methodAnnotations = methodAnnotations == null ? List.of() : List.copyOf(methodAnnotations);
        extendsType = extendsType == null ? "" : extendsType.trim();
        implementsTypes = implementsTypes == null ? List.of() : List.copyOf(implementsTypes);
    }

    public CoderChangesPayload(String id, String project, String targetFile, String export, String method,
            String language, String framework, String signature, String returns, String kind,
            List<String> members, List<String> imports, String body, List<String> missing,
            boolean executed) {
        this(id, project, targetFile, export, method, language, framework, signature, returns, kind,
            members, imports, body, missing, List.of(), List.of(), executed, "", List.of());
    }

    public CoderChangesPayload(String id, String project, String targetFile, String export, String method,
            String language, String framework, String signature, String returns, String kind,
            List<String> members, List<String> imports, String body, List<String> missing,
            List<String> annotations, List<String> methodAnnotations, boolean executed) {
        this(id, project, targetFile, export, method, language, framework, signature, returns, kind,
            members, imports, body, missing, annotations, methodAnnotations, executed, "", List.of());
    }
}
