// Figma sandbox — receives ops from UI iframe, creates/updates/deletes nodes, reads tree

figma.showUI(__html__, { width: 320, height: 420 });

interface FillData {
  r: number; g: number; b: number; a?: number;
}

interface StrokeData {
  r: number; g: number; b: number; a?: number;
  weight?: number; align?: "INSIDE" | "OUTSIDE" | "CENTER";
}

interface DropShadowData {
  color?: { r: number; g: number; b: number; a?: number };
  offset?: { x: number; y: number };
  radius?: number;
}

interface OpData {
  op: string;
  tempId: string;
  parentTempId?: string;
  parentNodeId?: string;
  nodeId?: string;
  name?: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  fills?: FillData[];
  stroke?: StrokeData;
  opacity?: number;
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
  dropShadow?: DropShadowData;
  text?: string;
  fontSize?: number;
  fontFamily?: string;
  fontWeight?: string;
  textAlignHorizontal?: "LEFT" | "CENTER" | "RIGHT" | "JUSTIFIED";
  textAutoResize?: "NONE" | "WIDTH_AND_HEIGHT" | "HEIGHT" | "TRUNCATE";
  lineHeight?: number;
  letterSpacing?: number;
  visible?: boolean;
  layoutSizingHorizontal?: "FIXED" | "HUG" | "FILL";
  layoutSizingVertical?: "FIXED" | "HUG" | "FILL";
}

const FONT_LOAD_TIMEOUT_MS = 10000;

function loadFontWithTimeout(
  fontName: FontName,
  timeoutMs: number = FONT_LOAD_TIMEOUT_MS
): Promise<void> {
  return Promise.race([
    figma.loadFontAsync(fontName),
    new Promise<never>(function(_, reject) {
      setTimeout(function() {
        reject(new Error(
          "Font load timed out after " + timeoutMs + "ms for " +
          fontName.family + " " + fontName.style +
          ". Check that this font is available in your Figma file."
        ));
      }, timeoutMs);
    }),
  ]);
}

function toFigmaFills(fills?: FillData[]): SolidPaint[] | undefined {
  if (!fills || fills.length === 0) return undefined;
  return fills.map(function(f) {
    return {
      type: "SOLID" as const,
      color: { r: f.r, g: f.g, b: f.b },
      opacity: f.a !== undefined ? f.a : 1,
    };
  });
}

function applyFills(node: GeometryMixin, fills?: FillData[]) {
  var paints = toFigmaFills(fills);
  if (paints) node.fills = paints;
}

function applyStroke(node: GeometryMixin & MinimalStrokesMixin, stroke?: StrokeData) {
  if (!stroke) return;
  var paint: SolidPaint = {
    type: "SOLID",
    color: { r: stroke.r, g: stroke.g, b: stroke.b },
    opacity: stroke.a !== undefined ? stroke.a : 1,
  };
  node.strokes = [paint];
  node.strokeWeight = stroke.weight !== undefined ? stroke.weight : 1;
  if (stroke.align) {
    node.strokeAlign = stroke.align;
  }
}

function applyDropShadow(node: BlendMixin, shadow?: DropShadowData) {
  if (!shadow) return;
  var color = shadow.color || { r: 0, g: 0, b: 0, a: 0.25 };
  var offset = shadow.offset || { x: 0, y: 4 };
  var effect: DropShadowEffect = {
    type: "DROP_SHADOW",
    visible: true,
    blendMode: "NORMAL",
    color: { r: color.r, g: color.g, b: color.b, a: color.a !== undefined ? color.a : 0.25 },
    offset: { x: offset.x, y: offset.y },
    radius: shadow.radius !== undefined ? shadow.radius : 4,
    spread: 0,
  };
  node.effects = [effect];
}

function resolveParent(
  op: OpData,
  tempIdMap: Map<string, SceneNode>
): BaseNode & ChildrenMixin {
  if (op.parentNodeId) {
    var found = figma.getNodeById(op.parentNodeId);
    if (found && "children" in found) {
      return found as BaseNode & ChildrenMixin;
    }
    throw new Error("parentNodeId '" + op.parentNodeId + "' not found or cannot have children");
  }
  if (op.parentTempId) {
    var parent = tempIdMap.get(op.parentTempId);
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
  var tempIdMap = new Map<string, SceneNode>();
  var resultMap: Record<string, string> = {};

  for (var i = 0; i < ops.length; i++) {
    var op = ops[i];
    try {
      // Handle UPDATE_NODE
      if (op.op === "UPDATE_NODE") {
        if (!op.nodeId) throw new Error("UPDATE_NODE requires nodeId");
        var target = figma.getNodeById(op.nodeId);
        if (!target) throw new Error("Node '" + op.nodeId + "' not found");

        if (op.name !== undefined) target.name = op.name;
        if (op.x !== undefined && "x" in target) (target as any).x = op.x;
        if (op.y !== undefined && "y" in target) (target as any).y = op.y;
        if (op.w !== undefined && op.h !== undefined && "resize" in target) {
          (target as any).resize(op.w, op.h);
        } else if (op.w !== undefined && "resize" in target) {
          (target as any).resize(op.w, (target as any).height);
        } else if (op.h !== undefined && "resize" in target) {
          (target as any).resize((target as any).width, op.h);
        }
        if (op.fills && "fills" in target) applyFills(target as any, op.fills);
        if (op.stroke && "strokes" in target) applyStroke(target as any, op.stroke);
        if (op.opacity !== undefined && "opacity" in target) (target as any).opacity = op.opacity;
        if (op.cornerRadius !== undefined && "cornerRadius" in target) {
          (target as any).cornerRadius = op.cornerRadius;
        }
        if (op.visible !== undefined && "visible" in target) (target as any).visible = op.visible;
        if (op.layoutSizingHorizontal && "layoutSizingHorizontal" in target) {
          (target as any).layoutSizingHorizontal = op.layoutSizingHorizontal;
        }
        if (op.layoutSizingVertical && "layoutSizingVertical" in target) {
          (target as any).layoutSizingVertical = op.layoutSizingVertical;
        }

        // Text-specific updates
        if (op.text !== undefined && target.type === "TEXT") {
          var textTarget = target as TextNode;
          var family = op.fontFamily || (textTarget.fontName as FontName).family;
          var style = op.fontWeight || (textTarget.fontName as FontName).style;
          await loadFontWithTimeout({ family: family, style: style });
          textTarget.fontName = { family: family, style: style };
          textTarget.characters = op.text;
          if (op.fontSize) textTarget.fontSize = op.fontSize;
        } else if ((op.fontFamily || op.fontWeight || op.fontSize) && target.type === "TEXT") {
          var textTarget2 = target as TextNode;
          var family2 = op.fontFamily || (textTarget2.fontName as FontName).family;
          var style2 = op.fontWeight || (textTarget2.fontName as FontName).style;
          await loadFontWithTimeout({ family: family2, style: style2 });
          textTarget2.fontName = { family: family2, style: style2 };
          if (op.fontSize) textTarget2.fontSize = op.fontSize;
        }

        resultMap[op.tempId] = target.id;
        continue;
      }

      // Handle DELETE_NODE
      if (op.op === "DELETE_NODE") {
        if (!op.nodeId) throw new Error("DELETE_NODE requires nodeId");
        var toDelete = figma.getNodeById(op.nodeId);
        if (!toDelete) throw new Error("Node '" + op.nodeId + "' not found for deletion");
        if (toDelete.parent) {
          toDelete.remove();
        }
        resultMap[op.tempId] = op.nodeId;
        continue;
      }

      // Create ops
      var node: SceneNode;
      var parent = resolveParent(op, tempIdMap);

      switch (op.op) {
        case "CREATE_FRAME": {
          var frame = figma.createFrame();
          if (op.w != null || op.h != null) {
            frame.resize(op.w || 100, op.h || 100);
          }
          if (op.cornerRadius) frame.cornerRadius = op.cornerRadius;
          if (op.layoutMode && op.layoutMode !== "NONE") {
            frame.layoutMode = op.layoutMode;
          }
          if (op.itemSpacing !== undefined) frame.itemSpacing = op.itemSpacing;
          if (op.paddingLeft !== undefined) frame.paddingLeft = op.paddingLeft;
          if (op.paddingRight !== undefined) frame.paddingRight = op.paddingRight;
          if (op.paddingTop !== undefined) frame.paddingTop = op.paddingTop;
          if (op.paddingBottom !== undefined) frame.paddingBottom = op.paddingBottom;
          if (op.primaryAxisAlignItems) frame.primaryAxisAlignItems = op.primaryAxisAlignItems;
          if (op.counterAxisAlignItems) frame.counterAxisAlignItems = op.counterAxisAlignItems;
          if (op.clipsContent !== undefined) frame.clipsContent = op.clipsContent;
          if (op.opacity !== undefined) frame.opacity = op.opacity;
          applyFills(frame, op.fills);
          applyStroke(frame, op.stroke);
          applyDropShadow(frame, op.dropShadow);
          node = frame;
          break;
        }

        case "CREATE_RECTANGLE": {
          var rect = figma.createRectangle();
          rect.resize(op.w || 100, op.h || 100);
          if (op.cornerRadius) rect.cornerRadius = op.cornerRadius;
          if (op.opacity !== undefined) rect.opacity = op.opacity;
          applyFills(rect, op.fills);
          applyStroke(rect, op.stroke);
          node = rect;
          break;
        }

        case "CREATE_ELLIPSE": {
          var ellipse = figma.createEllipse();
          ellipse.resize(op.w || 100, op.h || 100);
          if (op.opacity !== undefined) ellipse.opacity = op.opacity;
          applyFills(ellipse, op.fills);
          applyStroke(ellipse, op.stroke);
          node = ellipse;
          break;
        }

        case "CREATE_TEXT": {
          var textNode = figma.createText();
          var tfamily = op.fontFamily || "Inter";
          var tstyle = op.fontWeight || "Regular";
          await loadFontWithTimeout({ family: tfamily, style: tstyle });
          textNode.fontName = { family: tfamily, style: tstyle };
          textNode.characters = op.text || "";
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
          applyStroke(textNode, op.stroke);
          node = textNode;
          break;
        }

        default:
          throw new Error("Unknown op type: " + op.op);
      }

      if (op.name) node.name = op.name;
      node.x = op.x || 0;
      node.y = op.y || 0;
      parent.appendChild(node);

      // Apply layout sizing AFTER appendChild (Figma requires parent context)
      if (op.layoutSizingHorizontal || op.layoutSizingVertical) {
        // Explicit sizing provided — apply it
        if (op.layoutSizingHorizontal && "layoutSizingHorizontal" in node) {
          (node as any).layoutSizingHorizontal = op.layoutSizingHorizontal;
        }
        if (op.layoutSizingVertical && "layoutSizingVertical" in node) {
          (node as any).layoutSizingVertical = op.layoutSizingVertical;
        }
      } else if (op.op === "CREATE_FRAME" && op.layoutMode && op.layoutMode !== "NONE" && op.w == null && op.h == null) {
        // Auto-layout frame with no explicit w/h/sizing → default to HUG
        (node as FrameNode).layoutSizingHorizontal = "HUG";
        (node as FrameNode).layoutSizingVertical = "HUG";
      }

      tempIdMap.set(op.tempId, node);
      resultMap[op.tempId] = node.id;
    } catch (err: any) {
      figma.ui.postMessage({
        type: "job-error",
        jobId: jobId,
        error: "Op " + i + " (" + op.op + ", tempId=" + op.tempId + "): " + (err.message || err),
      });
      return;
    }
  }

  figma.ui.postMessage({
    type: "job-complete",
    jobId: jobId,
    result: { tempIdMap: resultMap },
  });
}

function serializeNode(node: BaseNode, depth: number): any {
  var data: any = {
    id: node.id,
    name: node.name,
    type: node.type,
  };

  if ("x" in node) data.x = (node as any).x;
  if ("y" in node) data.y = (node as any).y;
  if ("width" in node) data.width = (node as any).width;
  if ("height" in node) data.height = (node as any).height;

  // Rich property serialization
  if ("opacity" in node && (node as any).opacity !== 1) {
    data.opacity = (node as any).opacity;
  }
  if ("cornerRadius" in node && (node as any).cornerRadius > 0) {
    data.cornerRadius = (node as any).cornerRadius;
  }
  if ("visible" in node && !(node as any).visible) {
    data.visible = false;
  }

  // Fills — extract solid color info
  if ("fills" in node) {
    var fills = (node as any).fills;
    if (fills && fills.length > 0 && fills[0].type === "SOLID") {
      var f = fills[0];
      data.fill = {
        r: Math.round(f.color.r * 1000) / 1000,
        g: Math.round(f.color.g * 1000) / 1000,
        b: Math.round(f.color.b * 1000) / 1000,
      };
      if (f.opacity !== undefined && f.opacity !== 1) {
        data.fill.a = Math.round(f.opacity * 1000) / 1000;
      }
    }
  }

  // Text properties
  if (node.type === "TEXT") {
    var tn = node as TextNode;
    data.text = tn.characters;
    if (typeof tn.fontSize === "number") data.fontSize = tn.fontSize;
    if (tn.fontName && typeof tn.fontName !== "symbol") {
      var fn = tn.fontName as FontName;
      data.fontFamily = fn.family;
      data.fontWeight = fn.style;
    }
  }

  // Auto-layout info
  if ("layoutMode" in node) {
    var lm = (node as any).layoutMode;
    if (lm && lm !== "NONE") {
      data.layoutMode = lm;
      data.itemSpacing = (node as any).itemSpacing;
    }
  }

  // Layout sizing (only include non-FIXED values)
  if ("layoutSizingHorizontal" in node) {
    var lsh = (node as any).layoutSizingHorizontal;
    if (lsh && lsh !== "FIXED") data.layoutSizingHorizontal = lsh;
  }
  if ("layoutSizingVertical" in node) {
    var lsv = (node as any).layoutSizingVertical;
    if (lsv && lsv !== "FIXED") data.layoutSizingVertical = lsv;
  }

  if (depth > 0 && "children" in node) {
    data.children = (node as any).children.map(function(c: BaseNode) {
      return serializeNode(c, depth - 1);
    });
  }

  return data;
}

function readNodeTree(requestId: string, depth: number) {
  var page = figma.currentPage;
  var tree = serializeNode(page, depth);
  figma.ui.postMessage({
    type: "read-response",
    requestId: requestId,
    data: tree,
  });
}

async function takeScreenshot(requestId: string, nodeId: string, scale: number) {
  try {
    var node: SceneNode | null = null;

    if (nodeId) {
      var found = figma.getNodeById(nodeId);
      if (!found) {
        throw new Error("Node '" + nodeId + "' not found");
      }
      if (found.type === "PAGE" || found.type === "DOCUMENT") {
        throw new Error("Cannot export PAGE or DOCUMENT nodes. Specify a frame or layer node ID.");
      }
      node = found as SceneNode;
    } else {
      // Try current selection, then first top-level frame
      var sel = figma.currentPage.selection;
      if (sel.length > 0) {
        node = sel[0];
      } else {
        var children = figma.currentPage.children;
        if (children.length > 0) {
          node = children[0];
        }
      }
    }

    if (!node) {
      throw new Error("No node to screenshot. Select a node or pass a node_id.");
    }

    var bytes = await node.exportAsync({
      format: "PNG",
      constraint: { type: "SCALE", value: scale },
    });

    // Convert Uint8Array to binary string (sandbox lacks btoa)
    var binaryStr = "";
    for (var i = 0; i < bytes.length; i++) {
      binaryStr += String.fromCharCode(bytes[i]);
    }

    figma.ui.postMessage({
      type: "screenshot-response",
      requestId: requestId,
      binaryStr: binaryStr,
    });
  } catch (err: any) {
    figma.ui.postMessage({
      type: "screenshot-error",
      requestId: requestId,
      error: err.message || String(err),
    });
  }
}

figma.ui.onmessage = function(msg: any) {
  if (msg.type === "execute-ops") {
    executeOps(msg.jobId, msg.ops);
  } else if (msg.type === "read-node-tree") {
    readNodeTree(msg.requestId, msg.depth);
  } else if (msg.type === "screenshot-request") {
    takeScreenshot(msg.requestId, msg.nodeId, msg.scale);
  }
};
