// App.js
import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import Home from './pages/Home';
import AdminPage from './pages/AdminPage';

const App = () => {
  return (
    <Router>
      <Switch>
        <Route exact path='/' component={Home} />
        <Route path='/admin' component={AdminPage} />
      </Switch>
    </Router>
  );
};

export default App;