define('OutSystems/ClientRuntime/RuntimeDebuggerAPI',["require", "exports"], function (require, exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.BreakpointType = void 0;
    var BreakpointType;
    (function (BreakpointType) {
        BreakpointType[BreakpointType["Normal"] = 0] = "Normal";
        BreakpointType[BreakpointType["AtFunctionReturn"] = 1] = "AtFunctionReturn";
        BreakpointType[BreakpointType["BetweenAssignments"] = 2] = "BetweenAssignments";
    })(BreakpointType || (exports.BreakpointType = BreakpointType = {}));
});
// All licensing information regarding this source code can be found in the LICENSES.txt file.
//# sourceMappingURL=NullDebugger.js.map?ts=1774635038238
define('OutSystems/ClientRuntime/VersionDefinition',["require", "exports"], function (require, exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.toObject = exports.registerPackage = exports.clientRuntimeKey = void 0;
    var versions = new Map();
    exports.clientRuntimeKey = "Client Runtime Packages";
    var cacheResult;
    function registerPackage(project, version) {
        cacheResult = null;
        versions.set(project, version);
    }
    exports.registerPackage = registerPackage;
    function toObject() {
        if (!cacheResult) {
            var result_1 = { "Client Runtime Packages": "" };
            versions.forEach(function (version, project) {
                if (version && project) {
                    result_1[exports.clientRuntimeKey] += "".concat(project, "= ").concat(version, ";");
                }
            });
            cacheResult = result_1;
        }
        return cacheResult;
    }
    exports.toObject = toObject;
});
//# sourceMappingURL=VersionDefinition.js.map;
define('OutSystems/ClientRuntime/NullDebugger',["require", "exports", "./RuntimeDebuggerAPI", "./VersionDefinition"], function (require, exports, RuntimeDebuggerAPI_1, VersionDefinition) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.Version = exports.NullDebugger = void 0;
    var NullDebugger = (function () {
        function NullDebugger() {
        }
        NullDebugger.prototype.startSession = function () { };
        NullDebugger.prototype.endSession = function () { };
        NullDebugger.prototype.getThreadStack = function (callContextId) {
            return null;
        };
        NullDebugger.prototype.addBreakpoint = function (breakpointId) { };
        NullDebugger.prototype.addBreakpoints = function (breakpointIds) { };
        NullDebugger.prototype.allowBreakpointsFromModule = function (key) { };
        NullDebugger.prototype.removeBreakpoint = function (breakpointId) { };
        NullDebugger.prototype.clearBreakpoints = function () { };
        NullDebugger.prototype.continue = function (callContextId) { };
        NullDebugger.prototype.continueToHere = function (breakpointId, callContextId) { };
        NullDebugger.prototype.stepInto = function (callContextId) { };
        NullDebugger.prototype.stepOver = function (callContextId) { };
        NullDebugger.prototype.stepOut = function (callContextId) { };
        NullDebugger.prototype.pauseOnAllExceptions = function (isEnabled) { };
        NullDebugger.prototype.evaluateVariable = function (callContextId, stackLevel, actionKey, variableKey, path, depth) {
            return null;
        };
        Object.defineProperty(NullDebugger.prototype, "version", {
            get: function () {
                return 0;
            },
            enumerable: false,
            configurable: true
        });
        NullDebugger.prototype.isPausedOnException = function () {
            return false;
        };
        NullDebugger.prototype.getExceptionMessage = function (callContextId) {
            return null;
        };
        NullDebugger.prototype.getThreadStartName = function (callContextId) {
            return null;
        };
        NullDebugger.prototype.initialize = function (waitForClient) {
            return Promise.resolve();
        };
        NullDebugger.prototype.registerMetaInfo = function (variablesMapping) { };
        NullDebugger.prototype.getRequestHeaders = function (callContextId) {
            return null;
        };
        NullDebugger.prototype.processResponseHeaders = function (callContextId, headers) { };
        NullDebugger.prototype.setThreadStartName = function (callContextId, threadStartName) { };
        NullDebugger.prototype.push = function (breakpointIdStr, moduleName, elementName, elementType, callContextId, varBag) { };
        NullDebugger.prototype.pop = function (breakpointIdStr, callContextId) { };
        NullDebugger.prototype.handleFunctionCall = function (functionCaller, resultType, callContextId) {
            return functionCaller();
        };
        NullDebugger.prototype.handleBreakpoint = function (breakpointIdStr, callContextId, breakpointType, extraInfo) {
            var dummy = RuntimeDebuggerAPI_1.BreakpointType.Normal;
            return true;
        };
        NullDebugger.prototype.handleException = function (error, callContextId) { };
        NullDebugger.prototype.parse = function (breakpointIdStr) {
            return null;
        };
        Object.defineProperty(NullDebugger.prototype, "BreakpointType", {
            get: function () {
                return RuntimeDebuggerAPI_1.BreakpointType;
            },
            enumerable: false,
            configurable: true
        });
        return NullDebugger;
    }());
    exports.NullDebugger = NullDebugger;
    exports.Version = "3.67.0";
    VersionDefinition.registerPackage("client-runtime-core", exports.Version);
    var globalObj = typeof window !== "undefined" ? window : global;
    globalObj.OutSystemsDebugger = new NullDebugger();
});
//# sourceMappingURL=NullDebugger.js.map;
