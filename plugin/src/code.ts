// Figma sandbox — receives ops from UI iframe, creates nodes, reads tree

figma.showUI(__html__, { width: 320, height: 420 });

interface OpData {
  op: string;
  tempId: string;
  parentTempId?: string;
  parentNodeId?: string;
  name?: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  fills?: Array<{ r: number; g: number; b: number; a?: number }>;
  cornerRadius?: number;
  layoutMode?: "NONE" | "HORIZONTAL" | "VERTICAL";
  itemSpacing?: number;
  paddingLeft?: number;
  paddingRight?: number;
  paddingTop?: number;
  paddingBottom?: number;
  primaryAxisAlignItems?: "MIN" | "CENTER" | "MAX" | "SPACE_BETWEEN";
  counterAxisAlignItems?: "MIN" | "CENTER" | "MAX";
  clipsContent?: boolean;
  opacity?: number;
  text?: string;
  fontSize?: number;
  fontFamily?: string;
  fontWeight?: string;
  textAlignHorizontal?: "LEFT" | "CENTER" | "RIGHT" | "JUSTIFIED";
  textAutoResize?: "NONE" | "WIDTH_AND_HEIGHT" | "HEIGHT" | "TRUNCATE";
  lineHeight?: number;
  letterSpacing?: number;
}

function applyFills(node: GeometryMixin, fills?: OpData["fills"]) {
  if (!fills || fills.length === 0) return;
  const paints: SolidPaint[] = fills.map((f) => ({
    type: "SOLID",
    color: { r: f.r, g: f.g, b: f.b },
    opacity: f.a ?? 1,
  }));
  node.fills = paints;
}

function resolveParent(
  op: OpData,
  tempIdMap: Map<string, SceneNode>
): BaseNode & ChildrenMixin {
  if (op.parentNodeId) {
    const node = figma.getNodeById(op.parentNodeId);
    if (node && "children" in node) {
      return node as BaseNode & ChildrenMixin;
    }
    throw new Error("parentNodeId '" + op.parentNodeId + "' not found or cannot have children");
  }
  if (op.parentTempId) {
    const parent = tempIdMap.get(op.parentTempId);
    if (parent && "children" in parent) {
      return parent as BaseNode & ChildrenMixin;
    }
  }
  return figma.currentPage;
}

async function executeOps(
  jobId: string,
  ops: OpData[]
): Promise<void> {
  const tempIdMap = new Map<string, SceneNode>();
  const resultMap: Record<string, string> = {};

  for (let i = 0; i < ops.length; i++) {
    const op = ops[i];
    try {
      let node: SceneNode;
      const parent = resolveParent(op, tempIdMap);

      switch (op.op) {
        case "CREATE_FRAME": {
          const frame = figma.createFrame();
          frame.resize(op.w ?? 100, op.h ?? 100);
          if (op.cornerRadius) frame.cornerRadius = op.cornerRadius;
          if (op.layoutMode && op.layoutMode !== "NONE") {
            frame.layoutMode = op.layoutMode;
            frame.primaryAxisSizingMode = "AUTO";
            frame.counterAxisSizingMode = "AUTO";
          }
          if (op.itemSpacing !== undefined) frame.itemSpacing = op.itemSpacing;
          if (op.paddingLeft !== undefined) frame.paddingLeft = op.paddingLeft;
          if (op.paddingRight !== undefined) frame.paddingRight = op.paddingRight;
          if (op.paddingTop !== undefined) frame.paddingTop = op.paddingTop;
          if (op.paddingBottom !== undefined) frame.paddingBottom = op.paddingBottom;
          if (op.primaryAxisAlignItems) frame.primaryAxisAlignItems = op.primaryAxisAlignItems;
          if (op.counterAxisAlignItems) frame.counterAxisAlignItems = op.counterAxisAlignItems;
          if (op.clipsContent !== undefined) frame.clipsContent = op.clipsContent;
          applyFills(frame, op.fills);
          node = frame;
          break;
        }

        case "CREATE_RECTANGLE": {
          const rect = figma.createRectangle();
          rect.resize(op.w ?? 100, op.h ?? 100);
          if (op.cornerRadius) rect.cornerRadius = op.cornerRadius;
          if (op.opacity !== undefined) rect.opacity = op.opacity;
          applyFills(rect, op.fills);
          node = rect;
          break;
        }

        case "CREATE_ELLIPSE": {
          const ellipse = figma.createEllipse();
          ellipse.resize(op.w ?? 100, op.h ?? 100);
          if (op.opacity !== undefined) ellipse.opacity = op.opacity;
          applyFills(ellipse, op.fills);
          node = ellipse;
          break;
        }

        case "CREATE_TEXT": {
          const textNode = figma.createText();
          const family = op.fontFamily ?? "Inter";
          const style = op.fontWeight ?? "Regular";
          await figma.loadFontAsync({ family, style });
          textNode.fontName = { family, style };
          textNode.characters = op.text ?? "";
          if (op.fontSize) textNode.fontSize = op.fontSize;
          if (op.textAlignHorizontal) textNode.textAlignHorizontal = op.textAlignHorizontal;
          if (op.textAutoResize) textNode.textAutoResize = op.textAutoResize;
          if (op.w !== undefined && op.h !== undefined) {
            textNode.resize(op.w, op.h);
          } else if (op.w !== undefined) {
            textNode.resize(op.w, textNode.height);
          }
          if (op.lineHeight !== undefined) {
            textNode.lineHeight = { value: op.lineHeight, unit: "PIXELS" };
          }
          if (op.letterSpacing !== undefined) {
            textNode.letterSpacing = { value: op.letterSpacing, unit: "PIXELS" };
          }
          if (op.opacity !== undefined) textNode.opacity = op.opacity;
          applyFills(textNode, op.fills);
          node = textNode;
          break;
        }

        default:
          throw new Error(`Unknown op type: ${op.op}`);
      }

      if (op.name) node.name = op.name;
      node.x = op.x ?? 0;
      node.y = op.y ?? 0;
      parent.appendChild(node);

      tempIdMap.set(op.tempId, node);
      resultMap[op.tempId] = node.id;
    } catch (err: any) {
      figma.ui.postMessage({
        type: "job-error",
        jobId,
        error: `Op ${i} (${op.op}, tempId=${op.tempId}): ${err.message || err}`,
      });
      return;
    }
  }

  figma.ui.postMessage({
    type: "job-complete",
    jobId,
    result: { tempIdMap: resultMap },
  });
}

function serializeNode(node: BaseNode, depth: number): any {
  const data: any = {
    id: node.id,
    name: node.name,
    type: node.type,
  };

  if ("x" in node) data.x = (node as any).x;
  if ("y" in node) data.y = (node as any).y;
  if ("width" in node) data.width = (node as any).width;
  if ("height" in node) data.height = (node as any).height;

  if (depth > 0 && "children" in node) {
    data.children = (node as any).children.map((c: BaseNode) =>
      serializeNode(c, depth - 1)
    );
  }

  return data;
}

function readNodeTree(requestId: string, depth: number) {
  const page = figma.currentPage;
  const tree = serializeNode(page, depth);
  figma.ui.postMessage({
    type: "read-response",
    requestId,
    data: tree,
  });
}

figma.ui.onmessage = (msg: any) => {
  if (msg.type === "execute-ops") {
    executeOps(msg.jobId, msg.ops);
  } else if (msg.type === "read-node-tree") {
    readNodeTree(msg.requestId, msg.depth);
  }
};
