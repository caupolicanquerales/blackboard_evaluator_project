package com.capo.McpServerApplication.config;

import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.capo.McpServerApplication.component.InitializrMcpTool;

@Configuration
public class McpToolConfig {

    @Bean
    public ToolCallbackProvider initializrTools(InitializrMcpTool initializrMcpTool) {
        return MethodToolCallbackProvider.builder()
                .toolObjects(initializrMcpTool)
                .build();
    }
}
