"use strict";
(() => {
  var __async = (__this, __arguments, generator) => {
    return new Promise((resolve, reject) => {
      var fulfilled = (value) => {
        try {
          step(generator.next(value));
        } catch (e) {
          reject(e);
        }
      };
      var rejected = (value) => {
        try {
          step(generator.throw(value));
        } catch (e) {
          reject(e);
        }
      };
      var step = (x) => x.done ? resolve(x.value) : Promise.resolve(x.value).then(fulfilled, rejected);
      step((generator = generator.apply(__this, __arguments)).next());
    });
  };

  // src/code.ts
  figma.showUI(__html__, { width: 320, height: 420 });
  function applyFills(node, fills) {
    if (!fills || fills.length === 0) return;
    const paints = fills.map((f) => {
      var _a;
      return {
        type: "SOLID",
        color: { r: f.r, g: f.g, b: f.b },
        opacity: (_a = f.a) != null ? _a : 1
      };
    });
    node.fills = paints;
  }
  function resolveParent(op, tempIdMap) {
    if (op.parentNodeId) {
      const node = figma.getNodeById(op.parentNodeId);
      if (node && "children" in node) {
        return node;
      }
      throw new Error("parentNodeId '" + op.parentNodeId + "' not found or cannot have children");
    }
    if (op.parentTempId) {
      const parent = tempIdMap.get(op.parentTempId);
      if (parent && "children" in parent) {
        return parent;
      }
    }
    return figma.currentPage;
  }
  function executeOps(jobId, ops) {
    return __async(this, null, function* () {
      var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j, _k;
      const tempIdMap = /* @__PURE__ */ new Map();
      const resultMap = {};
      for (let i = 0; i < ops.length; i++) {
        const op = ops[i];
        try {
          let node;
          const parent = resolveParent(op, tempIdMap);
          switch (op.op) {
            case "CREATE_FRAME": {
              const frame = figma.createFrame();
              frame.resize((_a = op.w) != null ? _a : 100, (_b = op.h) != null ? _b : 100);
              if (op.cornerRadius) frame.cornerRadius = op.cornerRadius;
              if (op.layoutMode && op.layoutMode !== "NONE") {
                frame.layoutMode = op.layoutMode;
                frame.primaryAxisSizingMode = "AUTO";
                frame.counterAxisSizingMode = "AUTO";
              }
              if (op.itemSpacing !== void 0) frame.itemSpacing = op.itemSpacing;
              if (op.paddingLeft !== void 0) frame.paddingLeft = op.paddingLeft;
              if (op.paddingRight !== void 0) frame.paddingRight = op.paddingRight;
              if (op.paddingTop !== void 0) frame.paddingTop = op.paddingTop;
              if (op.paddingBottom !== void 0) frame.paddingBottom = op.paddingBottom;
              if (op.primaryAxisAlignItems) frame.primaryAxisAlignItems = op.primaryAxisAlignItems;
              if (op.counterAxisAlignItems) frame.counterAxisAlignItems = op.counterAxisAlignItems;
              if (op.clipsContent !== void 0) frame.clipsContent = op.clipsContent;
              applyFills(frame, op.fills);
              node = frame;
              break;
            }
            case "CREATE_RECTANGLE": {
              const rect = figma.createRectangle();
              rect.resize((_c = op.w) != null ? _c : 100, (_d = op.h) != null ? _d : 100);
              if (op.cornerRadius) rect.cornerRadius = op.cornerRadius;
              if (op.opacity !== void 0) rect.opacity = op.opacity;
              applyFills(rect, op.fills);
              node = rect;
              break;
            }
            case "CREATE_ELLIPSE": {
              const ellipse = figma.createEllipse();
              ellipse.resize((_e = op.w) != null ? _e : 100, (_f = op.h) != null ? _f : 100);
              if (op.opacity !== void 0) ellipse.opacity = op.opacity;
              applyFills(ellipse, op.fills);
              node = ellipse;
              break;
            }
            case "CREATE_TEXT": {
              const textNode = figma.createText();
              const family = (_g = op.fontFamily) != null ? _g : "Inter";
              const style = (_h = op.fontWeight) != null ? _h : "Regular";
              yield figma.loadFontAsync({ family, style });
              textNode.fontName = { family, style };
              textNode.characters = (_i = op.text) != null ? _i : "";
              if (op.fontSize) textNode.fontSize = op.fontSize;
              if (op.textAlignHorizontal) textNode.textAlignHorizontal = op.textAlignHorizontal;
              if (op.textAutoResize) textNode.textAutoResize = op.textAutoResize;
              if (op.w !== void 0 && op.h !== void 0) {
                textNode.resize(op.w, op.h);
              } else if (op.w !== void 0) {
                textNode.resize(op.w, textNode.height);
              }
              if (op.lineHeight !== void 0) {
                textNode.lineHeight = { value: op.lineHeight, unit: "PIXELS" };
              }
              if (op.letterSpacing !== void 0) {
                textNode.letterSpacing = { value: op.letterSpacing, unit: "PIXELS" };
              }
              if (op.opacity !== void 0) textNode.opacity = op.opacity;
              applyFills(textNode, op.fills);
              node = textNode;
              break;
            }
            default:
              throw new Error(`Unknown op type: ${op.op}`);
          }
          if (op.name) node.name = op.name;
          node.x = (_j = op.x) != null ? _j : 0;
          node.y = (_k = op.y) != null ? _k : 0;
          parent.appendChild(node);
          tempIdMap.set(op.tempId, node);
          resultMap[op.tempId] = node.id;
        } catch (err) {
          figma.ui.postMessage({
            type: "job-error",
            jobId,
            error: `Op ${i} (${op.op}, tempId=${op.tempId}): ${err.message || err}`
          });
          return;
        }
      }
      figma.ui.postMessage({
        type: "job-complete",
        jobId,
        result: { tempIdMap: resultMap }
      });
    });
  }
  function serializeNode(node, depth) {
    const data = {
      id: node.id,
      name: node.name,
      type: node.type
    };
    if ("x" in node) data.x = node.x;
    if ("y" in node) data.y = node.y;
    if ("width" in node) data.width = node.width;
    if ("height" in node) data.height = node.height;
    if (depth > 0 && "children" in node) {
      data.children = node.children.map(
        (c) => serializeNode(c, depth - 1)
      );
    }
    return data;
  }
  function readNodeTree(requestId, depth) {
    const page = figma.currentPage;
    const tree = serializeNode(page, depth);
    figma.ui.postMessage({
      type: "read-response",
      requestId,
      data: tree
    });
  }
  figma.ui.onmessage = (msg) => {
    if (msg.type === "execute-ops") {
      executeOps(msg.jobId, msg.ops);
    } else if (msg.type === "read-node-tree") {
      readNodeTree(msg.requestId, msg.depth);
    }
  };
})();
