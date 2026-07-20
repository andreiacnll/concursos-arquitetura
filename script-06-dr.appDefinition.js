define("dr.appDefinition", ["OutSystems/ClientRuntime/Main"], function (OutSystems) {
var OS = OutSystems.Internal;
return {
environmentKey: "cd87793d-1e35-4f15-bd18-63b763ef9894",
environmentName: "DRE Production",
applicationKey: "fcd36108-ddf9-48cb-b99b-e83546f5ed19",
applicationName: "DRE",
userProviderName: "Users",
debugEnabled: false,
homeModuleName: "dr",
homeModuleKey: "2d40f63f-a850-4d97-a95f-1ce57291f9c8",
homeModuleControllerName: "dr.controller",
homeModuleLanguageResourcesName: "dr.languageResources",
defaultTransition: "Fade",
errorPageConfig: {
showExceptionStack: false
},
isWeb: true,
personalArea: null,
showWatermark: false
};
});
