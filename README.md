# Kala
Simple read-only REST API for mongoDB.

## FAQs

### What is this?

A very simple way of sticking a read only REST API on a single mongoDB database.  Useful, for example, for exposing some data where you want to manage that data through a separate interface or background process.

### How do I use it?

It's just a bottle app, so you can deploy it the same way you would any bottle app.  You'll also need to set the mongoDB connection URI and the name of the target database in the configuration.  An example configuration is included in the repository. It is also possible to use environment variables to configure Kala, the key variables are `KALA_MONGODB_URI`, `KALA_MONGODB_DB` and `KALA_CONFIGFILE`. If an environment variable is present it's value will be used over any supplied in the configuration file.

### Why wouldn't I just use SleepyMongoose? (https://github.com/10gen-labs/sleepy.mongoose/wiki)

You probably should, if you want a REST API to enable full CRUD against a mongoDB server.  As far as I can tell there's no way to lock sleepy.mongoose down so as to only allow reads and only allow a particular database, which is what this is designed to do.

### Why didn't you fork SleepyMongoose to add that feature then?

I could have done, but that seemed like considerably more effort than the tiny bottle app here.

### Why is it called Kala?

Dispatch war rocket 'Ajax' to bring back his body!
