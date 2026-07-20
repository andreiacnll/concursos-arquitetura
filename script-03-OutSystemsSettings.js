define('OutSystems/ClientRuntime/Settings',["require", "exports"], function (require, exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.getEnvParams = exports.setPlatformSettings = exports.EnvParam = void 0;
    var EnvParam;
    (function (EnvParam) {
        EnvParam.DbNullDatesTZAware = false;
        EnvParam.NullDatesTZAware = true;
        EnvParam.DateTimeRevamp = false;
        EnvParam.ForcePropagationParentToUndefined = false;
        EnvParam.EnableOnReadyTriggerFromBFCache = false;
        EnvParam.ClearScreenStateCacheOnSessionChange = true;
        EnvParam.AllowIndexedDBInWebKitIframes = true;
        EnvParam.ForceXhrCommunication = false;
        EnvParam.IndexedDBOffline = false;
        EnvParam.CanDisableAutoUpgrade = false;
        EnvParam.UseNewWebSQLImpl = false;
        EnvParam.ListItemIdWithoutModelId = false;
        EnvParam.SendEnvParamOnManifestRequest = false;
        EnvParam.UseNewJSONSerialization = false;
        EnvParam.CDNFilenameVersioning = false;
        EnvParam.AllowInterAppNavigationWhenAppIsRoot = true;
        EnvParam.EnableFixVirtualizationStackDetection = false;
        EnvParam.EnforceUnsafeEval = true;
        EnvParam.PreserveListItemReactKey = false;
        EnvParam.AllowTwoSequentialDotsInEmail = false;
        EnvParam.DisableRequestToECTProvider = false;
    })(EnvParam || (exports.EnvParam = EnvParam = {}));
    function setPlatformSettings(config) {
        for (var _i = 0, _a = Object.keys(config); _i < _a.length; _i++) {
            var k = _a[_i];
            EnvParam[k] = config[k];
        }
    }
    exports.setPlatformSettings = setPlatformSettings;
    function getEnvParams() {
        return EnvParam;
    }
    exports.getEnvParams = getEnvParams;
});
// All licensing information regarding this source code can be found in the LICENSES.txt file.
//# sourceMappingURL=OutSystemsSettings.js.map?ts=1774635038324
