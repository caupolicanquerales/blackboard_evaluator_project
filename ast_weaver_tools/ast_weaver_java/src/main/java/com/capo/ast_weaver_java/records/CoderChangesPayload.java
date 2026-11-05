package com.capo.ast_weaver_java.records;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
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
    boolean executed
) {

    public CoderChangesPayload {
        Objects.requireNonNull(targetFile, "targetFile is required");
        Objects.requireNonNull(export, "export is required");
        Objects.requireNonNull(method, "method is required");
        Objects.requireNonNull(body, "body is required");
        imports = imports == null ? List.of() : List.copyOf(imports);
        missing = missing == null ? List.of() : List.copyOf(missing);
        members = members == null ? List.of() : List.copyOf(members);
    }
}