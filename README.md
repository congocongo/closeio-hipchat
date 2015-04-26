# closeio-hipchat
A HipChat add-on to give details about a Close.io lead when its URL is mentioned in HipChat

## How to install
    # Download the repository.
    $ git clone https://github.com/elasticsales/closeio-hipchat.git
    ...
    $ cd closeio-hipchat
    
    # Create new heroku application
    $ heroku create <appname>
    
    # Attach PostgreSQL to an application
    $ heroku addons:add heroku-postgresql:hobby-dev
    
    # Set your addons URL
    heroku config HIPCHAT_ADDON_BASE_URL="https://my-addon.herokuapp.com/"
    
    # deploy it
    $ git push heroku master
    
Now, you're ready to install the add-on. 

