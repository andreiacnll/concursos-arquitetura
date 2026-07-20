require(["es6-promise", "tslib"], function (es6promise, tslib) {
require(["OutSystems/ClientRuntime/Main", "dr.appDefinition", "OutSystems/ClientRuntime/NullDebugger"], function (OutSystems, drAppDefinition, NullDebugger) {
var OS = OutSystems.Internal;
OS.Settings.setPlatformSettings({
IndexedDBOffline: false,
UseNewWebSQLImpl: false,
SendEnvParamOnManifestRequest: true,
AllowIndexedDBInWebKitIframes: true
});
if(OS.Navigation.ensureRequestSecurity()) {
return;
}

OS.Application.default.initialize(drAppDefinition, OS.Interfaces.Application.InitializationType.Full, new OS.Format.DateTimeFormatInfo("yyyy-MM-dd", "HH:mm:ss"), new OS.Format.NumberFormatInfo(".", ""), function () {
return Promise.all(["scripts/OutsystemsUI_DR.OutSystemsUI.js"].map(function (script) {
return OS.SystemActions.requireScript(script);
}));
}).then(function (success) {
function initViewPromise() {
return OS.Flow.promise(function (resolve, reject) {
require(["OutSystems/ReactView/Main"], function (OSView) {
try {OSView.Router.load(OS.Application.default);
resolve();
} catch (error) {
reject(error);
}

});
});
};
if(success) {
return initViewPromise();
}


}).catch(function (error) {
OS.ErrorHandling.handleError(error);
});
});
});

