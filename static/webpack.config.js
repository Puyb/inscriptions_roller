var ExtractTextPlugin = require("extract-text-webpack-plugin");
var HtmlWebpackPlugin = require("html-webpack-plugin");
var path = require("path");
var webpack = require("webpack");
var projectTemplatesRoot = "../../inscriptions/templates/";

module.exports = {
    context: path.resolve(__dirname, "src"),
    entry: {
        site: "./js/main.js",
        admin: "./js/admin.js",
    },
    output: {
        path: path.resolve(__dirname, "dist"),
        filename: "js/[name].js?[hash]",
        publicPath: "/static"
    },
    module: {
        loaders: [
            {
                test: /\.(gif|png|ico|jpg|svg)$/,
                include: [
                    path.resolve(__dirname, "src/images")
                ],
                loader: "file-loader?name=/images/[name].[ext]"
            },
            { test: /\.less$/, loader: ExtractTextPlugin.extract("style-loader", "css-loader!less-loader") },
            {
                test: /\.(woff|woff2|ttf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                include: [
                    path.resolve(__dirname, "/src/fonts"),
                    path.resolve(__dirname, "../node_modules")
                ],
                loader: "file-loader?name=/fonts/[name].[ext]?[hash]"
            },
            { test: /\.jsx?$/, loader: "babel-loader", query: {compact: false} },
        ]
    },
    resolve: {
        extensions: ["", ".js", ".jsx"],
    },
    plugins: [
        new webpack.IgnorePlugin(/^\.\/locale$/, /moment$/),
        new ExtractTextPlugin("css/[name].css?[hash]"),
        new HtmlWebpackPlugin({
            filename: projectTemplatesRoot + "_styles.html",
            templateContent: function(templateParams, compilation) {
                var link = "";
                for (var css in templateParams.htmlWebpackPlugin.files.css) {
                    link += "<link href='" + templateParams.htmlWebpackPlugin.files.css[css]  + "' rel='stylesheet' />\n"
                }
                return link;
            },
            chunks: ['site']
        }),
        new HtmlWebpackPlugin({
            filename: projectTemplatesRoot + "_scripts.html",
            templateContent: function(templateParams, compilation) {
                var script = "";
                for (var js in templateParams.htmlWebpackPlugin.files.js) {
                    script += "<script src='" + templateParams.htmlWebpackPlugin.files.js[js]  + "'></script>\n"
                }
                return script;
            },
            chunks: ['site']
        }),
        new HtmlWebpackPlugin({
            filename: projectTemplatesRoot + "admin/_styles.html",
            templateContent: function(templateParams, compilation) {
                var link = "";
                for (var css in templateParams.htmlWebpackPlugin.files.css) {
                    link += "<link href='" + templateParams.htmlWebpackPlugin.files.css[css]  + "' rel='stylesheet' />\n"
                }
                return link;
            },
            chunks: ['admin']
        }),
        new HtmlWebpackPlugin({
            filename: projectTemplatesRoot + "admin/_scripts.html",
            templateContent: function(templateParams, compilation) {
                var script = "";
                for (var js in templateParams.htmlWebpackPlugin.files.js) {
                    script += "<script src='" + templateParams.htmlWebpackPlugin.files.js[js]  + "'></script>\n"
                }
                return script;
            },
            chunks: ['admin']
        })
    ]
};
