'use strict';
angular.module('clientApp')
  .directive('marketCard', function ($compile) {
    return {
      templateUrl: 'scripts/directives/marketCard.html',
      restrict: 'E',
      scope: {
        market: '=data'
      },      
      link: function postLink(scope, element, attrs) {
        scope.openString = undefined;

        scope.weekdays = [
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday',
            'Friday',
            'Saturday',
            'Sunday'
        ];

        scope.getDate = function(date) {
            if(date.getDay() == 0)
                return 7;
            else
                return date.getDay();
        }      

        scope.compareDates = function(date1, date2) {
            if(date1.getFullYear() == date2.getFullYear() && date1.getMonth() == date2.getMonth() && date1.getDate() == date2.getDate())
                return true;
            else
                return false;
        }
        
        scope.generateOpeningString = function() {
            // Check if open today first
            for(var j = 0; j < scope.market.address.hours.length; j++) {
                var today = scope.getDate(new Date());
                if(scope.market.address.hours[j].weekday == today) {
                    scope.openString = "<strong><span class='glyphicon glyphicon-time'></span>&nbsp;<span class='hours-string'>Open today</span></strong> &#183; " + scope.market.address.hours[0].from_hour + ' - ' + scope.market.address.hours[0].to_hour;
                }
            }

            // If it's not open today, get the next day the market will be open
            if(scope.openString === undefined) {
                var today = scope.getDate(new Date());

                for(var j = 0; j < scope.market.address.hours.length; j++) {
                    var nextDayOpen = 0;
                    if(scope.market.address.hours[j].weekday >= today) {
                        nextDayOpen = j;

                        if(nextDayOpen < scope.market.address.hours.length) {
                            scope.openString = "<strong><span class='glyphicon glyphicon-time'></span>&nbsp;<span class='hours-string'>Open this " + scope.weekdays[scope.market.address.hours[nextDayOpen].weekday - 1] + "</span></strong> &#183; " +  scope.market.address.hours[nextDayOpen].from_hour + ' - ' + scope.market.address.hours[nextDayOpen].to_hour;
                            return;
                        }
                    }
                    scope.openString = "<strong><span class='glyphicon glyphicon-time'></span>&nbsp;<span class='hours-string'>Open next " + scope.weekdays[scope.market.address.hours[0].weekday - 1] + "</span></strong> &#183; " +  scope.market.address.hours[0].from_hour + ' - ' + scope.market.address.hours[0].to_hour;
                }                    
            }
        }

        scope.generateOpeningString();

      }
    };
  });