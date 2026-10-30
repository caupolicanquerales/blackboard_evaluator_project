import * as fs from "fs";
import * as path from "path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const PROJECTS_DIR = process.env.MCP_PROJECTS_DIR ?? "/workspace/projects";

// stdout is reserved for the MCP protocol, so logs go to stderr
function log(message: string): void {
  process.stderr.write(message + "\n");
}

function slugify(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "nestjs-app";
}

function timestamp(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-` +
    `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
  );
}

function buildPackageJson(name: string): string {
  return JSON.stringify(
    {
      name,
      version: "1.0.0",
      private: true,
      main: "dist/main.js",
      scripts: {
        build: "tsc -p tsconfig.json",
        start: "node dist/main.js",
      },
      dependencies: {
        "@nestjs/common": "^10.4.0",
        "@nestjs/core": "^10.4.0",
        "@nestjs/platform-express": "^10.4.0",
        "reflect-metadata": "^0.2.2",
        rxjs: "^7.8.1",
      },
      devDependencies: {
        "@types/node": "^20.14.0",
        typescript: "^5.5.4",
      },
    },
    null,
    2
  );
}

const TSCONFIG = JSON.stringify(
  {
    compilerOptions: {
      module: "commonjs",
      target: "ES2021",
      outDir: "dist",
      rootDir: "src",
      strict: false,
      esModuleInterop: true,
      experimentalDecorators: true,
      emitDecoratorMetadata: true,
      skipLibCheck: true,
    },
    include: ["src/**/*.ts"],
  },
  null,
  2
);

function mainTs(title: string): string {
  return `import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { Module, Controller, Get } from '@nestjs/common';

@Controller()
class AppController {
  @Get()
  root() {
    return { message: 'Hello from ${title}' };
  }

  @Get('health')
  health() {
    return { status: 'ok' };
  }
}

@Module({ controllers: [AppController] })
class AppModule {}

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  await app.listen(process.env.PORT ? Number(process.env.PORT) : 3000);
}

bootstrap();
`;
}

const GITIGNORE = `node_modules/
dist/
.env
`;

const server = new McpServer({
  name: "nestjs-project-generator",
  version: "1.0.0",
});

server.tool(
  "create_nestjs_project",
  "Generate a NestJS project skeleton in the shared projects folder, validate its files, and report the result.",
  { project_name: z.string().default("hello-nestjs") },
  async ({ project_name }) => {
    const slug = slugify(project_name);
    const folderName = `${slug}-${timestamp()}`;
    const projectDir = path.join(PROJECTS_DIR, folderName);
    const title = slug
      .split("-")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");

    log(`Creating NestJS project at ${projectDir}`);
    try {
      fs.mkdirSync(path.join(projectDir, "src"), { recursive: true });
      fs.writeFileSync(path.join(projectDir, "package.json"), buildPackageJson(slug));
      fs.writeFileSync(path.join(projectDir, "tsconfig.json"), TSCONFIG);
      fs.writeFileSync(path.join(projectDir, "src", "main.ts"), mainTs(title));
      fs.writeFileSync(path.join(projectDir, ".gitignore"), GITIGNORE);
      fs.writeFileSync(
        path.join(projectDir, "README.md"),
        `# ${title}\n\nGenerated NestJS project.\n\n## Run\n\n    npm install\n    npm run build\n    npm start\n`
      );
    } catch (exc) {
      return {
        content: [{ type: "text", text: `PROJECT FAILED: could not write files to ${projectDir}: ${String(exc)}` }],
        isError: true,
      };
    }

    // Validate that the generated JSON files parse correctly
    try {
      JSON.parse(fs.readFileSync(path.join(projectDir, "package.json"), "utf-8"));
      JSON.parse(fs.readFileSync(path.join(projectDir, "tsconfig.json"), "utf-8"));
    } catch (exc) {
      return {
        content: [{ type: "text", text: `PROJECT FAILED: generated JSON is invalid: ${String(exc)}` }],
        isError: true,
      };
    }

    log(`Project ready: ${folderName}`);
    return {
      content: [
        {
          type: "text",
          text:
            `PROJECT READY: ${folderName}\n` +
            `Path: ${projectDir}\n` +
            `Files: package.json, tsconfig.json, src/main.ts, README.md, .gitignore\n` +
            `Check: JSON VALID\n` +
            `Run: npm install && npm run build && npm start`,
        },
      ],
    };
  }
);

async function main(): Promise<void> {
  fs.mkdirSync(PROJECTS_DIR, { recursive: true });
  log(`NestJS MCP server starting, projects dir: ${PROJECTS_DIR}`);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  log(`Fatal: ${String(err)}`);
  process.exit(1);
});
