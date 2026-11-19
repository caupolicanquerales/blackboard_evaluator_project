package com.pulsestream.telemetry;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import javax.xml.parsers.DocumentBuilderFactory;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

class PomManifestTest {

    private static final String BOOT = "org.springframework.boot";

    private static Map<String, String> scopesByCoordinate() throws Exception {
        Document doc = DocumentBuilderFactory.newInstance().newDocumentBuilder()
                .parse(Path.of("pom.xml").toFile());
        Element project = doc.getDocumentElement();
        Map<String, String> result = new java.util.HashMap<>();
        for (Element deps : children(project, "dependencies")) {
            for (Element dep : children(deps, "dependency")) {
                String scope = children(dep, "scope").stream().findFirst().map(Element::getTextContent)
                        .orElse("compile");
                result.put(text(dep, "groupId") + ":" + text(dep, "artifactId"), scope.trim());
            }
        }
        return result;
    }

    private static String text(Element parent, String name) {
        return children(parent, name).get(0).getTextContent().trim();
    }

    private static List<Element> children(Element parent, String name) {
        List<Element> out = new ArrayList<>();
        NodeList nodes = parent.getChildNodes();
        for (int i = 0; i < nodes.getLength(); i++) {
            if (nodes.item(i) instanceof Element e && e.getTagName().equals(name)) {
                out.add(e);
            }
        }
        return out;
    }

    @Test
    void pom_scaffoldStarters_remainWithCompileScope() throws Exception {
        Map<String, String> scopes = scopesByCoordinate();

        assertThat(scopes)
                .containsEntry(BOOT + ":spring-boot-starter-webflux", "compile")
                .containsEntry(BOOT + ":spring-boot-starter-data-r2dbc", "compile")
                .containsEntry(BOOT + ":spring-boot-starter-actuator", "compile")
                .containsEntry(BOOT + ":spring-boot-starter-validation", "compile")
                .containsEntry("org.flywaydb:flyway-core", "compile");
    }

    @Test
    void pom_h2_hasTestScope() throws Exception {
        assertThat(scopesByCoordinate()).containsEntry("com.h2database:h2", "test");
    }

    @Test
    void pom_securityStarter_hasCompileScope() throws Exception {
        assertThat(scopesByCoordinate()).containsEntry(BOOT + ":spring-boot-starter-security", "compile");
    }

    @Test
    void pom_securityTest_hasTestScope() throws Exception {
        assertThat(scopesByCoordinate()).containsEntry("org.springframework.security:spring-security-test", "test");
    }
}
